import json
import logging
import os
from copy import deepcopy
from hashlib import md5
from typing import Union, Iterable, List

from filelock import FileLock, Timeout
from typing_extensions import override

from kag.interface import LLMClient, VectorizeModelABC, EmbeddingVector

logger = logging.getLogger()


class CacheManager:
    lock_dict = {}
    params_dict = {}

    def register(self, cache_root: str, params: dict) -> str:
        if not cache_root:
            cache_root = os.path.join(os.getcwd(), '.cache')
            if params and 'model' in params:
                cache_root = os.path.join(cache_root, params.get('model'))

        self.lock_dict[cache_root] = FileLock(os.path.join(cache_root, 'lockfile.lock'))
        self.params_dict[cache_root] = self.normalize_value(params, remove_keys=['api_key'])
        return cache_root

    def unregister(self, cache_root: str):
        self.lock_dict.pop(cache_root)

    def read(self, cache_root: str, cache_key: Union[str, dict, list]) -> any:
        lock = self.lock_dict[cache_root]
        if lock is None:
            logger.error('cache_root not registered: {}', cache_root)
            return None

        fullname = os.path.join(cache_root, self.get_cache_filename(cache_key))
        if not os.path.exists(fullname):
            return None
        os.makedirs(os.path.dirname(fullname), exist_ok=True)

        try:
            with lock.acquire(timeout=5):
                with open(fullname, 'r', encoding='utf-8') as f:
                    json_content = f.read()
                content = json.loads(json_content)
                return content['response']

        except Timeout:
            logger.error('cache file locked: {}', fullname)
            return None

    def write(self, cache_root: str, prompt: Union[str, dict, list], response: str):
        lock = self.lock_dict[cache_root]
        if lock is None:
            logger.error('cache_root not registered: {}', cache_root)
            return

        fullname = os.path.join(cache_root, self.get_cache_filename(prompt))
        os.makedirs(os.path.dirname(fullname), exist_ok=True)

        content = json.dumps(self.normalize_value({
            'request': {
                'prompt': prompt, 'params': self.params_dict[cache_root]
            },
            'response': response
        }, remove_keys=[]), ensure_ascii=False, indent=4)
        try:
            with lock.acquire(timeout=5):
                with open(fullname, 'w', encoding='utf-8') as f:
                    f.write(content)
        except Timeout:
            logger.error('cache file locked: {}', fullname)
            return None
        pass

    def delete(self, cache_root: str, filename: str):
        lock = self.lock_dict[cache_root]
        if lock is None:
            logger.error('cache_root not registered: {}', cache_root)
            return
        try:
            with lock.acquire(timeout=5):
                if os.path.exists(filename):
                    os.remove(filename)
        except Timeout:
            logger.error('cache file locked: {}', filename)
            return None
        pass

    @staticmethod
    def get_cache_filename(cache_key: Union[str, dict, list]) -> str:
        if isinstance(cache_key, dict):
            prop_keys = [str(x) for x in cache_key.keys()]
            prop_keys.sort(key=lambda x: x)
            normalized_key = json.dumps({
                x: cache_key.get(x) for x in prop_keys
            }, ensure_ascii=False)
        else:
            normalized_key = json.dumps(cache_key, ensure_ascii=False)

        md5_digest = md5()
        md5_digest.update(normalized_key.encode('utf-8'))
        md5_filename = md5_digest.hexdigest()
        return f'{md5_filename[:2]}/{md5_filename}.json'

    def normalize_value(self, value: any, remove_keys: List[str]):
        if isinstance(value, dict):
            return {
                k: self.normalize_value(v, remove_keys) for k, v in value.items() if v and k not in remove_keys
            }
        else:
            return value


CACHE_MGR = CacheManager()


@LLMClient.register("cacheable")
@LLMClient.register("cacheable_llm")
class CacheableLLMClient(LLMClient):
    """
    A client class for delegate LLM
    """

    def __init__(self, delegate_type: str, cache_root: str = None, **kwargs):
        name = kwargs.pop("name", None)
        if not name:
            name = f"cacheable_llm"

        super().__init__(name=name, **kwargs)

        self.cache_root = CACHE_MGR.register(cache_root, kwargs)

        config = deepcopy(kwargs)
        config['type'] = delegate_type
        self.client = LLMClient.from_config(config)

        self.check()

    def __delete__(self, instance):
        CACHE_MGR.unregister(self.cache_root)

    @override
    def __call__(self, prompt: Union[str, dict, list], **kwargs) -> str:
        response = CACHE_MGR.read(self.cache_root, prompt)
        if response is None:
            response = self.client(prompt, **kwargs)
            CACHE_MGR.write(self.cache_root, prompt, response)
        return response

    @override
    def check(self):
        self.client.check()

    pass


@VectorizeModelABC.register("cacheable_vectorize_model")
class CacheableVectorizeModel(VectorizeModelABC):
    """
    A class that extends the VectorizeModelABC base class.
    """

    def __init__(self,
                 delegate_type: str,
                 cache_root: str = None,
                 vector_dimensions: int = None,
                 max_rate: float = 1000,
                 time_period: float = 1,
                 **kwargs):
        name = kwargs.pop("name", None)
        if not name:
            name = f"cacheable_vectorize_model"

        super().__init__(name=name, vector_dimensions=vector_dimensions, max_rate=max_rate, time_period=time_period)

        self.cache_root = CACHE_MGR.register(cache_root, kwargs)

        config = deepcopy(kwargs)
        config['type'] = delegate_type
        self.client = VectorizeModelABC.from_config(config)

    def __delete__(self, instance):
        CACHE_MGR.unregister(self.cache_root)

    def vectorize(self, texts: Union[str, Iterable[str]]) -> Union[EmbeddingVector, Iterable[EmbeddingVector]]:
        source_texts: list[str] = [texts] if isinstance(texts, str) else texts
        embedding_vectors = [CACHE_MGR.read(self.cache_root, x) for x in source_texts]

        uncached_texts = [text for text, embedding_vector in zip(source_texts, embedding_vectors) if
                          embedding_vector is None]
        if len(uncached_texts) > 0:
            vectors: Iterable[EmbeddingVector] = self.client.vectorize(uncached_texts)

            for idx, (text, embedding_vector) in enumerate(zip(source_texts, embedding_vectors)):
                if embedding_vector is None:
                    embedding_vectors[idx] = vectors[0]
                    vectors = vectors[1:]
                    CACHE_MGR.write(self.cache_root, text, embedding_vectors[idx])
            pass

        if isinstance(texts, str):
            return embedding_vectors[0]
        else:
            return embedding_vectors

    pass

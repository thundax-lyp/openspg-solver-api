from typing import List, Dict, Tuple

from typing_extensions import override

from kag.interface import LLMClient
from kag.interface import PromptABC, VectorizeModelABC
from kag.solver.retriever.chunk_retriever import ChunkRetriever
from kag.solver.retriever.impl.default_chunk_retrieval import DefaultChunkRetriever
from kag.solver.tools.graph_api.graph_api_abc import GraphApiABC
from kag.solver.tools.search_api.search_api_abc import SearchApiABC


@ChunkRetriever.register("custom_chunk_retriever")
class DefaultChunkRetriever(DefaultChunkRetriever):
    def __init__(
            self,
            ner_prompt: PromptABC = None,
            std_prompt: PromptABC = None,
            pagerank_threshold: float = 0.9,
            match_threshold: float = 0.9,
            pagerank_weight: float = 0.5,
            recall_num: int = 10,
            rerank_topk: int = 10,
            reranker_model_path: str = None,
            vectorize_model: VectorizeModelABC = None,
            graph_api: GraphApiABC = None,
            search_api: SearchApiABC = None,
            llm_client: LLMClient = None,
            **kwargs,
    ):
        super().__init__(
            ner_prompt=ner_prompt,
            std_prompt=std_prompt,
            pagerank_threshold=pagerank_threshold,
            match_threshold=match_threshold,
            pagerank_weight=pagerank_weight,
            recall_num=recall_num,
            rerank_topk=rerank_topk,
            reranker_model_path=reranker_model_path,
            vectorize_model=vectorize_model,
            graph_api=graph_api,
            search_api=search_api,
            llm_client=llm_client,
            **kwargs,
        )

    @override
    def named_entity_recognition(self, query: str):
        entities = super().named_entity_recognition(query)
        return [x for x in entities if self.validate(x, [
            ('category', str), ('name', str)
        ])]

    @override
    def named_entity_standardization(self, query: str, entities: List[Dict]):
        normalized_entities = super().named_entity_standardization(query, entities)
        return [x for x in normalized_entities if self.validate(x, [
            ('category', str), ('name', str), ('office_name', str)
        ])]

    @staticmethod
    def validate(target: any, rules: List[Tuple[str, type]]) -> bool:
        if not isinstance(target, dict):
            return False

        for (property_name, property_type) in rules:
            property_value = target.get(property_name)
            if property_value is None:
                return False
            if not isinstance(property_value, property_type):
                return False

        return True

    pass

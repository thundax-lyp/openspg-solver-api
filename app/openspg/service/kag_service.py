import json
import logging
import os.path
import threading
import traceback
from abc import ABC
from typing import Generator

from kag.common.conf import KAGConstants, KAG_CONFIG, KAG_PROJECT_CONF, load_config
from kag.common.registry import import_modules_from_path
from kag.interface import SolverPipelineABC
from kag.solver.reporter.open_spg_reporter import OpenSPGReporter
from knext.project.client import ProjectClient

from app.utils import remove_empty_fields

logger = logging.getLogger()


class EventQueue(Generator, ABC):
    """
    A queue that can be used to send events to a generator.
    Stop iteration while got a 'None' event
    """

    def __init__(self):
        self.events = []
        self.lock = threading.Lock()

    def __next__(self):
        if len(self.events) > 0:
            with self.lock:
                event = self.events.pop(0)
            if event is None:
                raise StopIteration
            return event

    def send(self, event: any):
        with self.lock:
            self.events.append(event)

    def throw(self, typ, val=None, tb=None):
        pass


class EventReporter(OpenSPGReporter):

    def __init__(self, printer, **kwargs):
        super().__init__(0, **kwargs)
        self.printer = printer

    def add_report_line(self, segment, tag_name, content, status, **kwargs):
        super().add_report_line(segment, tag_name, content, status, **kwargs)

        report_data = self.report_stream_data[tag_name]

        if self.printer:
            self.printer(remove_empty_fields({
                'event': 'changed',
                'data': {
                    k: v for k, v in report_data.items() if k not in ['kwargs']
                }
            }))

    pass


def load_configs_from_file(root_dir: str):
    """
    load kag_config.yaml from kag_config_dir
    """
    config_filenames = []
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".yml") or filename.endswith(".yaml"):
                config_filenames.append(os.path.join(dirpath, filename))
    logger.info(f"find {len(config_filenames)} yaml files")

    configs = []
    for config_filename in config_filenames:
        config = load_config(config_file=config_filename)
        if config and config['project'] and config['project']['namespace']:
            configs.append(config)

    return configs


def load_projects_from_server(host_addr: str):
    project_client = ProjectClient(host_addr=host_addr, project_id=-1)
    return project_client.get_all()


def load_kag_config(host_addr, project_id):
    """
    copy those codes from kag.common.conf.load_config
    """
    project_client = ProjectClient(host_addr=host_addr, project_id=project_id)
    project = project_client.get_by_id(project_id)
    if not project:
        return {}
    config = json.loads(project.config)
    if "project" not in config:
        config["project"] = {
            KAGConstants.KAG_PROJECT_ID_KEY: project_id,
            KAGConstants.KAG_PROJECT_HOST_ADDR_KEY: host_addr,
            KAGConstants.KAG_NAMESPACE_KEY: project.namespace,
        }
        prompt_config = config.pop("prompt", {})
        for key in [KAGConstants.KAG_LANGUAGE_KEY, KAGConstants.KAG_BIZ_SCENE_KEY]:
            if key in prompt_config:
                config["project"][key] = prompt_config[key]
    if "vectorizer" in config and "vectorize_model" not in config:
        config["vectorize_model"] = config["vectorizer"]
    config["project"][KAGConstants.KAG_PROJECT_HOST_ADDR_KEY] = host_addr
    return config


class KagService:

    def __init__(self, service_url: str, config_dir: str, addition_modules: list[str] = None, ):
        self.service_url = service_url
        self.config_dir = config_dir

        import_modules_from_path(os.path.join(os.path.dirname(__file__), 'kag_additions'))
        for module in addition_modules or []:
            import_modules_from_path(module)

        self.config_map = {}
        self.load_project_list()
        self.trace_project_list()
        pass

    def load_project_list(self):
        configs = load_configs_from_file(self.config_dir)
        projects = load_projects_from_server(host_addr=self.service_url)

        for config in configs:
            project_name = config['project']['namespace']
            project_id = str(config['project']['id'])
            if project_name in projects and projects[project_name] == project_id:
                self.config_map[project_name] = config
        pass

    def trace_project_list(self):
        logger.info(f'find {len(self.config_map)} projects')
        for project_name in self.config_map:
            logger.info(f'  - {project_name}')

    def get_projects(self):
        return self.config_map

    def get_project_id_by_name(self, project_name: str):
        return self.config_map.get(project_name)

    async def query(self, query: str, project_name: str, printer=None):
        try:
            reporter = EventReporter(printer=printer)

            global_config = self.config_map[project_name]

            KAG_CONFIG.update_conf(global_config)
            KAG_PROJECT_CONF.project_id = global_config['project']['id']

            solver = SolverPipelineABC.from_config(global_config["kag_solver_pipeline"])
            return await solver.ainvoke(query, reporter=reporter)

        except Exception as e:
            traceback.print_exc()
            return str(e)
        pass


kag_service = None


def get_kag_service(service_url: str, config_dir: str, addition_modules: list[str] = None) -> KagService:
    global kag_service
    if kag_service is None:
        kag_service = KagService(service_url=service_url, config_dir=config_dir, addition_modules=addition_modules)
    return kag_service

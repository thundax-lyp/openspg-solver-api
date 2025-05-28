import json
import logging
import os.path
import threading
import traceback
from abc import ABC
from typing import Generator

from kag.common.conf import KAGConstants, KAG_CONFIG, KAG_PROJECT_CONF
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
                'data': report_data
            }))

    pass


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
    return config


class KagService:

    def __init__(self, service_url: str, addition_modules: list[str] = None):
        self.service_url = service_url

        import_modules_from_path(os.path.join(os.path.dirname(__file__), 'kag_additions'))
        for module in addition_modules or []:
            import_modules_from_path(module)

        self.project_client = ProjectClient(host_addr=self.service_url, project_id=-1)
        logger.info('loading projects')
        self.project_list = self.project_client.get_all()
        logger.info(f'loaded {len(self.project_list)} projects')
        for project_name, project_key in self.project_list.items():
            logger.info(f'  - {project_name}: {project_key}')
        pass

    def get_projects(self):
        return self.project_list

    def get_project_id_by_name(self, project_name: str):
        return self.project_list.get(project_name)

    async def query(self, query: str, project_id: str, printer = None):
        try:
            reporter = EventReporter(printer=printer)
            global_config = load_kag_config(self.service_url, project_id)

            KAG_CONFIG.update_conf(global_config)
            KAG_PROJECT_CONF.project_id = project_id

            solver_config = global_config["solver_pipeline"]
            solver = SolverPipelineABC.from_config(solver_config)
            return await solver.ainvoke(query, reporter=reporter)

        except Exception as e:
            traceback.print_exc()
            return str(e)
        pass


kag_service = None


def get_kag_service(service_url: str, addition_modules: list[str] = None) -> KagService:
    global kag_service
    if kag_service is None:
        kag_service = KagService(service_url=service_url, addition_modules=addition_modules)
    return kag_service


print(__file__)

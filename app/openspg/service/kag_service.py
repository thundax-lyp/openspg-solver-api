import asyncio
import concurrent.futures
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
from kag.solver.executor.retriever.local_knowledge_base.kag_retriever.kag_hybrid_executor import KAGRetrievedResponse
from kag.solver.reporter.open_spg_reporter import OpenSPGReporter
from kag.solver.reporter.trace_log_reporter import TraceLog
from knext.project.client import ProjectClient
from knext.reasoner.rest.models.report_pipeline_request import ReportPipelineRequest

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

    def __init__(self, generator: Generator, **kwargs):
        super().__init__(0, **kwargs)
        self.generator = generator

    def do_report(self):
        return self.generate_report_data()

    def generate_report_data(self):
        processed_report_record = []
        report_to_spg_data = TraceLog()
        status = ""
        segment_name = ""
        for report_id in self.report_record:
            if report_id in processed_report_record:
                continue
            report_data = self.report_stream_data[report_id]
            segment_name = report_data["segment"]
            content = report_data["content"]
            if segment_name == "thinker":
                report_to_spg_data.thinker[report_data["tag_name"]] = f"{content}"
            elif segment_name == "answer":
                report_to_spg_data.answer = content
            elif segment_name == "reference":
                if isinstance(content, KAGRetrievedResponse):
                    report_to_spg_data.decompose.append(content.to_dict())
                else:
                    logger.warning(f"Unknown reference type {type(content)}")
                    continue
            elif segment_name == "generator":
                report_to_spg_data.generator.append(content)
            elif segment_name == "generator_reference":
                report_to_spg_data.reference = content

            status = report_data["status"]
            processed_report_record.append(report_id)
            if status != "FINISH":
                break
        if status == "FINISH":
            if segment_name != "answer":
                status = "RUNNING"
        return report_to_spg_data, status

    def reasoner_dialog_report_node_post(self, report_pipeline_request: ReportPipelineRequest):
        self.generator.send(remove_empty_fields({
            'event': 'nodeChanged',
            'data': report_pipeline_request.to_dict()
        }))

    def reasoner_dialog_report_pipeline_post(self, report_pipeline_request: ReportPipelineRequest):
        self.generator.send(remove_empty_fields({
            'event': 'pipelineChanged',
            'data': report_pipeline_request.to_dict()
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
    config["project"]["project_id"] = project_id
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

    def query(self, query: str, project_id: str):
        event_queue = EventQueue()

        reporter = EventReporter(generator=event_queue)

        async def do_task():
            try:
                global_config = load_kag_config(self.service_url, project_id)

                KAG_CONFIG.update_conf(global_config)
                KAG_PROJECT_CONF.project_id = project_id

                solver_config = global_config["solver_pipeline"]
                solver = SolverPipelineABC.from_config(solver_config)
                answer = await solver.ainvoke(query, reporter=reporter)
                event_queue.send(answer)
            except Exception as e:
                event_queue.send(f'Error: {str(e)}')
                traceback.print_exc()
            event_queue.send(None)
            pass

        def do_task_sync():
            asyncio.run(do_task())

        with concurrent.futures.ThreadPoolExecutor() as executor:
            executor.submit(do_task_sync)

        yield from event_queue


kag_service = None


def get_kag_service(service_url: str, addition_modules: list[str] = None) -> KagService:
    global kag_service
    if kag_service is None:
        kag_service = KagService(service_url=service_url, addition_modules=addition_modules)
    return kag_service


print(__file__)

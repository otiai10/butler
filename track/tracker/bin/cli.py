#!/usr/bin/env python
from uuid import uuid4
import argparse
import os

from airflow.operators import TriggerDagRunOperator

from tracker.model.configuration import *
from tracker.model.analysis_run import *
from tracker.model.analysis import *
from tracker.model.workflow import *
import tracker.model


def set_up_dag_run(context, dag_run_obj):
    dag_run_obj.payload = {"config": context["config"]}
    dag_run_obj.run_id = str(uuid4())
    print context
    return dag_run_obj


def parse_args():
    my_parser = argparse.ArgumentParser()

    sub_parsers = my_parser.add_subparsers()

    common_args_parser = argparse.ArgumentParser(
        add_help=False, conflict_handler='resolve')
    help_str = "Flag indicating that config ID should be taken from config file name."
    common_args_parser.add_argument("-f", "--id_from_filename", dest="id_from_filename",
                                    help=help_str,
                                    action="store_true")

    create_workflow_parser = sub_parsers.add_parser(
        "create-workflow", parents=[common_args_parser], conflict_handler='resolve')
    create_workflow_parser.add_argument(
        "-n", "--workflow_name", help="Name of the workflow to create",
        dest="workflow_name", required=True)
    create_workflow_parser.add_argument(
        "-v", "--workflow_version", help="Version of the workflow to create",
        dest="workflow_version", required=True)
    create_workflow_parser.add_argument(
        "-c", "--config_file_location", help="Path to a config file for this workflow.",
        dest="config_file_location", required=True)
    create_workflow_parser.set_defaults(func=create_workflow_command)

    launch_workflow_parser = sub_parsers.add_parser(
        "launch-workflow", parents=[common_args_parser], conflict_handler='resolve')
    launch_workflow_parser.add_argument(
        "-w", "--workflow_id", help="ID of the workflow to run",
        dest="workflow_id", required=True)
    launch_workflow_parser.add_argument(
        "-a", "--analysis_id", help="ID of the analysis to run",
        dest="analysis_id", required=True)
    help_str = "Path to a directory that contains analysis run configuration files. Each file will generate one analysis run."
    launch_workflow_parser.add_argument(
        "-c", "--config_location", help=help_str,
        dest="config_location", required=False)
    launch_workflow_parser.set_defaults(func=launch_workflow_command)

    create_analysis_parser = sub_parsers.add_parser(
        "create-analysis", parents=[common_args_parser], conflict_handler='resolve')
    create_analysis_parser.add_argument(
        "-n", "--analysis_name", help="Name of the analysis to create",
        dest="analysis_name", required=True)
    create_analysis_parser.add_argument(
        "-d", "--analysis_start_date", help="Starting date of the analysis",
        dest="analysis_start_date", required=False)
    create_analysis_parser.add_argument(
        "-c", "--config_file_location", help="Path to a config file for this analysis.",
        dest="config_file_location", required=True)
    create_analysis_parser.set_defaults(func=create_analysis_command)

    update_config_parser = sub_parsers.add_parser(
        "update-config", parents=[common_args_parser], conflict_handler='resolve')
    my_group = update_config_parser.add_mutually_exclusive_group(required=True)
    my_group.add_argument(
        "-w", "--workflow_id", help="ID of the workflow to update.", dest="workflow_id")
    my_group.add_argument(
        "-a", "--analysis_id", help="ID of the analysis to update.", dest="analysis_id")
    update_config_parser.add_argument(
        "-c", "--config_file_location", help="Path to a config file.",
        dest="config_file_location", required=True)
    update_config_parser.set_defaults(func=update_config_command)

    get_number_of_runs_parser = sub_parsers.add_parser("get-run-count")
    get_number_of_runs_parser.add_argument(
        "-a", "--analysis_id",
        help="ID of the analysis to look up runs for",
        dest="analysis_id",
        required=True)
    get_number_of_runs_parser.add_argument("-s", "--run_status",
                                           help="Status of the analysis runs to look up",
                                           dest="run_status",
                                           choices=tracker.model.analysis_run.run_status_list,
                                           required=False)
    get_number_of_runs_parser.set_defaults(func=get_number_of_runs_command)

    my_args = my_parser.parse_args()

    return my_args


def make_config_from_args(args):
    config_file_location = args.config_file_location
    id_from_filename = args.id_from_filename

    if not os.path.isfile(config_file_location):
        raise ValueError("config_file_location must be a path to a file.")

    current_config = create_configuration_from_file(
        config_file_location, id_from_filename)

    return current_config.config_id


def create_workflow_command(args):
    workflow_name = args.workflow_name
    workflow_version = args.workflow_version

    current_config_id = make_config_from_args(args)

    my_workflow = create_workflow(
        workflow_name, workflow_version, current_config_id)

    print "Created workflow with ID: " + str(my_workflow.workflow_id)


def update_config_command(args):
    workflow_id = args.workflow_id
    analysis_id = args.analysis_id

    current_config_id = make_config_from_args(args)

    if workflow_id:
        set_configuration_for_workflow(workflow_id, current_config_id)
    elif analysis_id:
        set_configuration_for_analysis(analysis_id, current_config_id)


def create_analysis_command(args):
    analysis_name = args.analysis_name
    analysis_start_date = args.analysis_start_date
    config_file_location = args.config_file_location
    id_from_filename = args.id_from_filename

    if not os.path.isfile(config_file_location):
        raise ValueError("config_file_location must be a path to a file.")

    current_config = create_configuration_from_file(
        config_file_location, id_from_filename)

    my_analysis = create_analysis(
        analysis_name, analysis_start_date, current_config.config_id)

    print "Created analysis with ID: " + str(my_analysis.analysis_id)


def launch_workflow_command(args):

    config_location = args.config_location
    analysis_id = args.analysis_id
    workflow_id = args.workflow_id

    my_workflow = get_workflow_by_id(workflow_id)

    id_from_filename = args.id_from_filename

    if not os.path.isdir(config_location):
        raise ValueError("config_location must be a path to a directory")

    my_dag_run = TriggerDagRunOperator(
        trigger_dag_id=my_workflow.workflow_name,
        python_callable=set_up_dag_run,
        task_id="run_my_workflow",
        owner="airflow")

    for root, dirs, files in os.walk(config_location):

        for config_file in files:
            current_config = create_configuration_from_file(
                os.path.join(root, config_file), id_from_filename)

            current_analysis_run = create_analysis_run(
                analysis_id, current_config.config_id, workflow_id)
            set_scheduled(current_analysis_run)

            effective_config = get_effective_configuration(
                current_analysis_run.analysis_run_id)

            effective_config[
                "analysis_run_id"] = current_analysis_run.analysis_run_id

            my_dag_run.execute({"config": effective_config})


def get_number_of_runs_command(args):
    analysis_id = args.analysis_id
    run_status = get_run_status_from_string(args.run_status)
    num_runs = get_number_of_runs_with_status(analysis_id, run_status)
    print "There are {} analysis runs for analysis {}, with status {}".\
        format(num_runs, analysis_id, args.run_status)

if __name__ == '__main__':
    my_args = parse_args()
    my_args.func(my_args)

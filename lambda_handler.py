from unittest.mock import patch


def handler(event, context):
    from kedro.framework.project import configure_project
    node_to_run = event["node_name"]
    configure_project("spaceflights_steps_function")
    
    # Since _multiprocessing.SemLock is not implemented on lambda yet,
    # we mock it out so we could import the session. This has no impact on the correctness
    # of the pipeline, as each Lambda function runs a single Kedro node, hence no need for Lock
    # during import. For more information, please see this StackOverflow discussion:
    # https://stackoverflow.com/questions/34005930/multiprocessing-semlock-is-not-implemented-when-running-on-aws-lambda
    with patch("multiprocessing.Lock"):
        

        from kedro.framework.session import KedroSession

        with KedroSession.create(env="aws") as session:
            session.run(node_names=[node_to_run])
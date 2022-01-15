from kedro.pipeline import Pipeline, node

from .nodes import (
    evaluate_model,
    split_data,
    train_model
)

def create_pipeline(**kwargs):
    return Pipeline(
        [
            node(
                func=split_data,
                inputs=['master_table', 'parameters'],
                outputs=['X_train', 'X_test', 'y_train', 'y_test']
            ),
            node(
                func=train_model,
                inputs=['X_train', 'y_train'],
                outputs='regressor'
            ),
            node(
                func=evaluate_model,
                inputs=['regressor', 'X_test', 'y_test'],
                outputs=None
            )
        ]
    )
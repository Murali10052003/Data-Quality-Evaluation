import pandas as pd
from dqeval.dataframe import DqEvalDataFrame
from dqeval.results_collector import ResultsCollector

# Your data
df = pd.DataFrame({
    'vendorid': [1, 2, 2, 3],
    'name': ['A', 'B', 'B', None]
})

dqevaldf = DqEvalDataFrame(df)
collector = ResultsCollector(dqevaldf)

# Option A: run individual evals
collector.execute_eval('vendor', 'DupEval',   {'columns': ['vendorid']})
collector.execute_eval('vendor', 'EmptyEval', {'columns': ['name']})

# Option B: run from a control table
control = pd.DataFrame({
    'tablename': ['vendor', 'vendor'],
    'dqmethod':  ['DupEval', 'EmptyEval'],
    'config':    ['{"columns": ["vendorid"]}', '{"columns": ["name"]}']
})
results_df = collector.run_control_table(control)

# Inspect failing rows for a specific eval
error_rows = collector.get_error_records('vendor', 'EmptyEval', 'name')
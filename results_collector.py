import json
import pandas as pd
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union
from dqeval.dataframe import DqEvalDataFrame
from dqeval.base import BaseDQEval
from dqeval.evals.dup_eval import DupEval
from dqeval.evals.empty_eval import EmptyEval
from dqeval.evals.unique_eval import UniqueEval
from dqeval.evals.dtype_eval import DtypeEval
from dqeval.evals.stringformat_eval import StringFormatEval
from dqeval.evals.range_eval import RangeEval
from dqeval.evals.categoricalvalues_eval import CategoricalValuesEval
from dqeval.evals.statisticaldistribution_eval import StatisticalDistributionEval
from dqeval.evals.datafreshness_eval import DataFreshnessEval
from dqeval.evals.referential_integrity_eval import ReferentialIntegrityEval
from dqeval.evals.rowcount_eval import RowCountEval
from dqeval.evals.custom_eval import CustomEval
from dqeval.evals.schema_eval import SchemaValidationEval
from dqeval.evals.unicode_validation_eval import UnicodeValidationEval
from dqeval.evals.daterange_eval import DateRangeEval
from dqeval.evals.mojibake_eval import MojibakeEval

class ResultsCollector:
    """
    Collects and aggregates data quality evaluation results into a unified results table.
    
    Supports Pandas and Spark engines.
    Results table schema:
    - run_id: UUID for this evaluation run
    - table: Source table name
    - dqmethod: Evaluation method (DupEval, EmptyEval, etc.)
    - col: Column(s) evaluated
    - status: Success/Failed
    - run_timestamp: When evaluation ran
    - dqevalcount: Number of failed records
    """
    
    # Mapping of dqmethod names to eval classes
    EVAL_MAPPING = {
        'DupEval': DupEval,
        'EmptyEval': EmptyEval,
        'UniqueEval': UniqueEval,
        'DtypeEval': DtypeEval,
        'StringFormatEval': StringFormatEval,
        'RangeEval': RangeEval,
        'CategoricalValuesEval': CategoricalValuesEval,
        'StatisticalDistributionEval': StatisticalDistributionEval,
        'DataFreshnessEval': DataFreshnessEval,
        'ReferentialIntegrityEval': ReferentialIntegrityEval,
        'RowCountEval': RowCountEval,
        'CustomEval': CustomEval,
        'SchemaValidationEval': SchemaValidationEval,
        'UnicodeValidationEval': UnicodeValidationEval,
        'DateRangeEval': DateRangeEval,
        'MojibakeEval': MojibakeEval,
    }

    def __init__(self, dataframe: DqEvalDataFrame, run_id: Optional[str] = None):
        """
        Initialize results collector.
        
        Args:
            dataframe: DqEvalDataFrame to evaluate
            run_id: Optional UUID for tracking (auto-generated if not provided)
        """
        self.dataframe = dataframe
        self.run_id = run_id or str(uuid.uuid4())
        self.results = []
        self.error_records = {}

    def execute_eval(
        self,
        table_name: str,
        dqmethod: str,
        config: Dict,
        collect_errors: bool = True
    ) -> Dict:
        """
        Execute a single evaluation and collect results.
        
        Args:
            table_name: Name of table being evaluated
            dqmethod: Name of evaluation method (key in EVAL_MAPPING)
            config: Configuration dict for the eval
            collect_errors: Whether to collect error records (advanced mode)
        
        Returns:
            Result dict with status, count, etc.
        """
        if dqmethod not in self.EVAL_MAPPING:
            raise ValueError(f"Unknown dqmethod: {dqmethod}. Supported: {list(self.EVAL_MAPPING.keys())}")
        
        eval_class = self.EVAL_MAPPING[dqmethod]
        eval_instance = eval_class(self.dataframe, config=config, run_id=self.run_id)
        
        # Run evaluation with advanced mode to get error records
        evaluation_mode = "advanced" if collect_errors else "basic"
        result = eval_instance.run(evaluation=evaluation_mode)
        
        # Parse result (could be JSON string or tuple of (JSON, DataFrame))
        if isinstance(result, tuple):
            result_json_str, error_df = result
        else:
            result_json_str = result
            error_df = None
        
        # Parse JSON result
        result_dict = json.loads(result_json_str)
        
        # Extract column(s) from config
        col_str = self._extract_column_info(config)
        
        # Build row for results table
        row = {
            'run_id': self.run_id,
            'table': table_name,
            'dqmethod': dqmethod,
            'col': col_str,
            'status': result_dict.get('status', 'Unknown'),
            'run_timestamp': result_dict.get('run_timestamp'),
            'dqevalcount': result_dict.get('dqeval_failed_count', 0)
        }
        
        self.results.append(row)
        
        # Store error records for optional retrieval
        if error_df is not None:
            key = f"{table_name}_{dqmethod}_{col_str}"
            self.error_records[key] = error_df
        
        return row

    def _extract_column_info(self, config: Dict) -> str:
        """Extract column(s) from config and format as string."""
        if 'columns' in config:
            cols = config['columns']
            return ','.join(cols) if isinstance(cols, list) else str(cols)
        elif 'column' in config:
            return config['column']
        else:
            return 'N/A'

    def run_control_table(self, control_table: Union[pd.DataFrame, 'pyspark.sql.DataFrame']) -> Union[pd.DataFrame, 'pyspark.sql.DataFrame']:
        """
        Execute all evaluations from a control table.
        
        Expected control table schema:
        - tablename: str
        - dqmethod: str (eval method name)
        - config: dict (as JSON string or dict)
        
        Returns:
            Results table as DataFrame (Pandas or Spark depending on engine)
        """
        engine = self.dataframe.get_engine()
        
        # Convert to Pandas for processing if needed
        if engine == 'spark':
            control_pd = control_table.toPandas()
        else:
            control_pd = control_table
        
        # Process each row in control table
        for _, row in control_pd.iterrows():
            table_name = row['table_name']
            dqmethod = row['dqmethod']
            config = row.get('config', {})
            
            # Parse config if it's a JSON string
            if isinstance(config, str):
                config = json.loads(config)
            
            try:
                self.execute_eval(table_name, dqmethod, config)
            except Exception as e:
                import logging as _log
                _log.getLogger("results_collector").error(
                    "Eval error: %s on %s config=%s → %s", dqmethod, table_name, config, e
                )
                self.results.append({
                    'run_id': self.run_id,
                    'table': table_name,
                    'dqmethod': dqmethod,
                    'col': 'N/A',
                    'status': 'Error',
                    'run_timestamp': datetime.now().isoformat(),
                    'dqevalcount': 0
                })
        
        # Convert results to DataFrame
        results_df = pd.DataFrame(self.results)
        
        # Convert back to Spark if needed
        if engine == 'spark':
            from pyspark.sql import SparkSession
            spark = SparkSession.getActiveSession()
            return spark.createDataFrame(results_df)
        
        return results_df

    def get_results_dataframe(self) -> Union[pd.DataFrame, 'pyspark.sql.DataFrame']:
        """Get current results as DataFrame."""
        results_df = pd.DataFrame(self.results)
        engine = self.dataframe.get_engine()
        
        if engine == 'spark':
            from pyspark.sql import SparkSession
            spark = SparkSession.getActiveSession()
            return spark.createDataFrame(results_df)
        
        return results_df

    def get_error_records(self, table: str, dqmethod: str, col: str) -> Optional[Union[pd.DataFrame, 'pyspark.sql.DataFrame']]:
        """Retrieve error records for a specific evaluation."""
        key = f"{table}_{dqmethod}_{col}"
        return self.error_records.get(key)

    def get_summary(self) -> Dict:
        """Get summary statistics of evaluation results."""
        results_df = pd.DataFrame(self.results)
        return {
            'total_evals': len(results_df),
            'passed': (results_df['status'] == 'Success').sum(),
            'failed': (results_df['status'] == 'Failed').sum(),
            'errors': (results_df['status'] == 'Error').sum(),
            'total_failed_records': results_df['dqevalcount'].sum()
        }
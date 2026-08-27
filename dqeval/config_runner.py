import yaml
import json
import os
import uuid
from dqeval.dataframe import DqEvalDataFrame
from dqeval.evals.dup_eval import DupEval
from dqeval.evals.empty_eval import EmptyEval
from dqeval.evals.unique_eval import UniqueEval
from dqeval.evals.dtype_eval import DtypeEval
from dqeval.evals.stringformat_eval import StringFormatEval
from dqeval.evals.schema_eval import SchemaValidationEval
from dqeval.evals.range_eval import RangeEval
from dqeval.evals.categoricalvalues_eval import CategoricalValuesEval
from dqeval.evals.statisticaldistribution_eval import StatisticalDistributionEval
from dqeval.evals.datafreshness_eval import DataFreshnessEval
from dqeval.evals.referential_integrity_eval import ReferentialIntegrityEval
from dqeval.evals.rowcount_eval import RowCountEval
from dqeval.evals.custom_eval import CustomEval
from dqeval.evals.unicode_validation_eval import UnicodeValidationEval
from dqeval.evals.daterange_eval import DateRangeEval
from dqeval.evals.mojibake_eval import MojibakeEval

class DqEvalConfigRunner:
    """
    DQEvalConfigRunner
    ---------------
    Loads a YAML configuration file describing data quality evaluations,
    runs the evals on the provided DqEvalDataFrame, and emits results
    to a uniquely named JSON file in the current directory.

    Usage:
        runner = DQEvalConfigRunner()
        runner.run_evals_from_yaml(dqevaldf, "dqeval_config.yml")
    """

    @staticmethod
    def run_evals_from_yaml(dataframe, yaml_path=None, yaml_string=None, write_to_file=True, df_mapping=None):
        """
        Runs DQEval checks as specified in a YAML config file or YAML string.

        Parameters:
            dataframe: DqEvalDataFrame
            yaml_path: Path to YAML config file (optional)
            yaml_string: YAML config as a string (optional)
            Both yaml_path and yaml_string cannot be None; one must be provided.
            write_to_file: If True, writes results to a JSON file; if False, returns results as a JSON string
            df_mapping: A dictionary mapping reference DataFrame names to actual DataFrame objects (optional, used only for referentialintegrity)

        Returns:
            If write_to_file is False, returns the results as a JSON string.
            If write_to_file is True, writes results to a file and returns nothing.

        Raises:
            Exception with a helpful message if YAML or check config is invalid.
        """
        # Ensure dataframe is DquDataFrame
        if not isinstance(dataframe, DqEvalDataFrame):
            dataframe = DqEvalDataFrame(dataframe)
        # Only allow pandas, spark, ray engines for YAML-based checks
        allowed_engines = {"pandas", "spark", "ray"}
        engine = dataframe.get_engine() if hasattr(dataframe, "get_engine") else None
        if engine not in allowed_engines:
            raise Exception(f"YAML-based evals are only supported for pandas, spark, and ray engines. Detected engine: {engine}")

        # Load YAML config from file or string
        try:
            if yaml_string is not None:
                config = yaml.safe_load(yaml_string)
            elif yaml_path is not None:
                with open(yaml_path, "r") as f:
                    config = yaml.safe_load(f)
            else:
                raise Exception("Either yaml_path or yaml_string must be provided.")
        except Exception as e:
            raise Exception(f"Failed to load YAML config: {e}")

        run_id = config.get("run_id")
        evals = config.get("evals", [])
        results = []

        for idx, check_cfg in enumerate(evals):
            try:
                check_type = check_cfg["type"].lower()
                if check_type == "duplicate":
                    check = DupEval(dataframe, config=check_cfg, run_id=run_id)
                elif check_type == "empty":
                    check = EmptyEval(dataframe, config=check_cfg, run_id=run_id)
                elif check_type == "unique":
                    check = UniqueEval(dataframe, config=check_cfg, run_id=run_id)
                elif check_type == "dtype":
                    check = DtypeEval(dataframe, config=check_cfg, run_id=run_id)
                elif check_type == "stringformat":
                    check = StringFormatEval(dataframe, config=check_cfg, run_id=run_id)
                elif check_type == "schemavalidation":
                    check = SchemaValidationEval(dataframe, config=check_cfg, run_id=run_id)
                elif check_type == "range":
                    check = RangeEval(dataframe, config=check_cfg, run_id=run_id)
                elif check_type == "categoricalvalues":
                    check = CategoricalValuesEval(dataframe, config=check_cfg, run_id=run_id)
                elif check_type == "statisticaldistribution":
                    check = StatisticalDistributionEval(dataframe, config=check_cfg, run_id=run_id)
                elif check_type == "datafreshness":
                    check = DataFreshnessEval(dataframe, config=check_cfg, run_id=run_id)
                elif check_type == "referentialintegrity":
                    ref_df_name = check_cfg.get("reference_df")
                    if isinstance(ref_df_name, str) and df_mapping and ref_df_name in df_mapping:
                        check_cfg["reference_df"] = df_mapping[ref_df_name]
                    check = ReferentialIntegrityEval(dataframe, config=check_cfg, run_id=run_id)
                elif check_type == "rowcount":
                    check = RowCountEval(dataframe, config=check_cfg, run_id=run_id)
                elif check_type == "custom":
                    func_str = check_cfg.get("func")
                    if isinstance(func_str, str):
                        check_cfg["func"] = eval(func_str)
                    check = CustomEval(dataframe, config=check_cfg, run_id=run_id)
                elif check_type == "unicodevalidation":
                    # Resolve target_df from df_mapping when it is specified as
                    # a string name (YAML cannot embed a live DataFrame object).
                    tgt_name = check_cfg.get("target_df")
                    if isinstance(tgt_name, str) and df_mapping and tgt_name in df_mapping:
                        check_cfg["target_df"] = df_mapping[tgt_name]
                    check = UnicodeValidationEval(dataframe, config=check_cfg, run_id=run_id)
                elif check_type == "daterange":
                    check = DateRangeEval(dataframe, config=check_cfg, run_id=run_id)
                elif check_type == "mojibake":
                    check = MojibakeEval(dataframe, config=check_cfg, run_id=run_id)
                else:
                    raise ValueError(f"Unknown check type: {check_type}")

                result = check.run(evaluation="basic")
                result_dict = json.loads(result) if isinstance(result, str) else result
                # Before appending result_dict, sanitize dqu_eval_config
                eval_config = dict(check_cfg)  # shallow copy
                # Handle reference_df serialization
                if "reference_df" in eval_config:
                    eval_config["reference_df"] = ref_df_name
                # Handle func serialization for custom checks
                if "func" in eval_config:
                    eval_config["func"] = func_str
                # Handle target_df serialization for unicode validation
                if check_type == "unicodevalidation" and "target_df" in eval_config:
                    eval_config["target_df"] = tgt_name

                result_dict["dqeval_config"] = eval_config
                result_dict["dqeval_engine"] = engine

                results.append(result_dict)
                
            except Exception as e:
                results.append({
                    "status": "Error",
                    "check_index": idx,
                    "check_config": check_cfg,
                    "error_message": str(e),
                    "run_id": run_id
                })

        if write_to_file:
            results_path = f"dqeval_results-{uuid.uuid4()}.json"
            with open(results_path, "w") as f:
                json.dump(results, f, indent=2)
            print(f"DQEval results written to {os.path.abspath(results_path)}")
            return
        else:
            return json.dumps(results, indent=2)
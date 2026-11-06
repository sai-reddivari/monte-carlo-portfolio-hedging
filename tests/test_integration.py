"""Cross-boundary integration checks for shared study inputs and cached release views."""
from contextlib import redirect_stdout
from hashlib import sha256
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

import numpy as np
import pandas as pd

from hedging_harness import Book, hedge, load_study, simulate_paths
from hedging_harness.study import export_input_tables, input_tables, load_named_inputs

ROOT=Path(__file__).resolve().parents[1]
STUDY=ROOT/"config/illustrative_study.json"


class SharedInputIntegrationTests(unittest.TestCase):
    def _nonuniform_source(self,folder):
        raw=json.loads(STUDY.read_text())
        order=[2,0,1]
        for field in ("names","spots","strikes","notionals","pricing_vols"):
            raw["book"][field]=[raw["book"][field][i] for i in order]
        raw["book"]["spots"]=[203.,57.,130.]
        raw["book"]["strikes"]=[200.,55.,125.]
        raw["book"]["notionals"]=[60000.,130000.,210000.]
        raw["scenario"]["path_vols"]=[.31,.23,.29]
        corr=np.array(raw["scenario"]["correlation"])
        raw["scenario"]["correlation"]=corr[np.ix_(order,order)].tolist()
        raw["n_paths"]=32
        path=Path(folder)/"nonuniform_study.json"
        path.write_text(json.dumps(raw,indent=2)+"\n")
        return path,raw

    def test_named_view_preserves_nonuniform_values_and_simulation_identity(self):
        with tempfile.TemporaryDirectory() as folder:
            source,raw=self._nonuniform_source(folder)
            portfolio,scenario,config=load_named_inputs(source)
            expected_book,expected_config=load_study(source)
            names=tuple(portfolio)
            named_book=Book(
                names=names,spots=tuple(portfolio[name]["spot"] for name in names),
                strikes=tuple(portfolio[name]["strike"] for name in names),
                notionals=tuple(portfolio[name]["notional"] for name in names),
                pricing_vols=tuple(portfolio[name]["pricing_vol"] for name in names),
                steps=portfolio[names[0]]["days_to_expiration"],
                sessions_per_year=portfolio[names[0]]["days_in_trading_year"],
                rate=portfolio[names[0]]["risk_free_rate"],
            )
            corr=pd.DataFrame(np.eye(len(names)),index=names,columns=names)
            for (left,right),value in scenario["correlations"].items():
                corr.loc[left,right]=value
                corr.loc[right,left]=value
            named_paths=simulate_paths(named_book,[scenario["path_vols"][name] for name in names],
                                       corr.to_numpy(),n_paths=32,seed=19)
            expected_paths=simulate_paths(expected_book,**expected_config["scenario"],n_paths=32,seed=19)
            np.testing.assert_array_equal(named_paths,expected_paths)
            named_result=hedge(named_book,named_paths,hedge_every=5,cost_bps=5)
            expected_result=hedge(expected_book,expected_paths,hedge_every=5,cost_bps=5)
            np.testing.assert_array_equal(named_result.terminal_pnl,expected_result.terminal_pnl)
            self.assertEqual(names,tuple(raw["book"]["names"]))
            self.assertEqual(config["shared_input_source"]["sha256"],sha256(source.read_bytes()).hexdigest())
            self.assertNotEqual(list(scenario["path_vols"].values()),list(raw["book"]["pricing_vols"]))

    def test_derived_tables_have_valid_foreign_keys_and_signed_quantities_after_shuffling(self):
        with tempfile.TemporaryDirectory() as folder:
            source,raw=self._nonuniform_source(folder)
            tables=input_tables(source)
            underlyings=tables["underlyings"].sample(frac=1,random_state=1)
            instruments=tables["instruments"].sample(frac=1,random_state=2)
            positions=tables["positions"].sample(frac=1,random_state=3)
            observations=tables["model_observations"].sample(frac=1,random_state=4)
            self.assertTrue(underlyings.underlying_id.is_unique)
            self.assertTrue(instruments.instrument_id.is_unique)
            self.assertTrue(set(instruments.underlying_id).issubset(underlyings.underlying_id))
            self.assertTrue(set(positions.instrument_id).issubset(instruments.instrument_id))
            self.assertFalse(observations.market_observed.any())
            joined=positions.merge(instruments,on="instrument_id",validate="one_to_one",suffixes=("_position","_instrument"))
            joined=joined.merge(observations,on="underlying_id",validate="one_to_one")
            expected_notionals=dict(zip(raw["book"]["names"],raw["book"]["notionals"]))
            self.assertTrue(joined.signed_quantity.lt(0).all())
            np.testing.assert_array_equal(joined.multiplier_position,joined.multiplier_instrument)
            reconstructed=-joined.signed_quantity*joined.multiplier_position*joined.spot
            np.testing.assert_allclose(reconstructed,joined.underlying_id.map(expected_notionals),rtol=1e-12)
            self.assertTrue(joined.kind.eq("call").all())
            self.assertTrue(joined.exercise.eq("European").all())
            self.assertTrue(joined.settlement.eq("cash").all())
            self.assertTrue(joined.expiry_convention.eq("relative_to_experiment_start").all())
            self.assertTrue(joined.source_sha256.eq(sha256(source.read_bytes()).hexdigest()).all())

    def test_exported_views_and_source_manifest_match_file_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            source,_=self._nonuniform_source(folder)
            destination=Path(folder)/"derived"
            record=export_input_tables(source,destination)
            self.assertTrue(record["derived_views_only"])
            self.assertEqual(record["source"]["sha256"],sha256(source.read_bytes()).hexdigest())
            for name,digest in record["files_sha256"].items():
                self.assertEqual(digest,sha256((destination/name).read_bytes()).hexdigest())
            self.assertEqual(json.loads((destination/"manifest.json").read_text()),record)


class CachedReleaseNotebookIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The same cached-lock contract now belongs to the package, not notebook code.
        cls.artifact_source = ("from hedging_harness.notebook_views import load_cached_release\n"
            "RELEASE_DIR, selected, selection, evaluation, gate = load_cached_release(PROTOCOL, study_path, RELEASE_DIR, ROOT, RUN_NEW_EXPERIMENT=RUN_NEW_EXPERIMENT, run_release=run_release)\n")

    def _fixture(self,folder):
        root=Path(folder)
        protocol=root/"protocol_source.json"
        study=root/"study_source.json"
        protocol.write_text('{"protocol":"current"}\n')
        study.write_text('{"study":"current"}\n')
        release=root/"release"
        release.mkdir()
        selection={"selected_policy":"locked_policy"}
        (release/"selection.json").write_text(json.dumps(selection)+"\n")
        selection_hash=sha256((release/"selection.json").read_bytes()).hexdigest()
        (release/"gate_status.json").write_text(json.dumps({"status":"complete","selection_lock_sha256":selection_hash})+"\n")
        commitment={"protocol_sha256":sha256(protocol.read_bytes()).hexdigest(),
                    "study_sha256":sha256(study.read_bytes()).hexdigest()}
        (release/"protocol_commitment.json").write_text(json.dumps(commitment)+"\n")
        # Evaluation deliberately makes another rule look better; cached lock must remain authoritative.
        pd.DataFrame({"policy":["locked_policy","tempting_evaluation_rule"],"loss_es95":[100.,1.]}).to_csv(release/"selection_metrics.csv",index=False)
        pd.DataFrame({"policy":["locked_policy","tempting_evaluation_rule"],"loss_es95":[100.,0.]}).to_csv(release/"evaluation_metrics.csv",index=False)
        manifest={path.name:sha256(path.read_bytes()).hexdigest() for path in release.iterdir() if path.is_file()}
        (release/"artifact_manifest.json").write_text(json.dumps(manifest)+"\n")
        run_new=Mock(side_effect=AssertionError("Cached report must not rerun or reselect."))
        namespace={"RUN_NEW_EXPERIMENT":False,"RELEASE_DIR":release,"ROOT":root,
                   "PROTOCOL":protocol,"study_path":study,"json":json,"sha256":sha256,
                   "pd":pd,"run_release":run_new}
        return namespace,run_new,protocol,study

    def test_default_cached_report_never_reruns_or_reselects_from_evaluation(self):
        with tempfile.TemporaryDirectory() as folder:
            namespace,run_new,_,_=self._fixture(folder)
            with redirect_stdout(io.StringIO()):
                exec(compile(self.artifact_source,"notebook04-cached-cell","exec"),namespace)
            run_new.assert_not_called()
            self.assertEqual(namespace["selected"],"locked_policy")

    def test_cached_report_rejects_changed_current_protocol_or_shared_source(self):
        for source_name in ("protocol","study"):
            with self.subTest(source=source_name),tempfile.TemporaryDirectory() as folder:
                namespace,run_new,protocol,study=self._fixture(folder)
                source=protocol if source_name=="protocol" else study
                source.write_text('{"changed":"after cached release"}\n')
                with redirect_stdout(io.StringIO()),self.assertRaises((AssertionError,ValueError,RuntimeError)):
                    exec(compile(self.artifact_source,"notebook04-cached-cell","exec"),namespace)
                run_new.assert_not_called()


if __name__=="__main__":unittest.main()

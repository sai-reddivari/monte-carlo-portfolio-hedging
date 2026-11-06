"""Selection/evaluation separation and truthful research-release completion."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from hedging_harness.research import load_protocol, run_release, select_policy
from hedging_harness.study import load_named_inputs

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / 'config/research_release_1.json'


class ResearchTests(unittest.TestCase):
    def test_shared_source_round_trips_names_and_correlations(self):
        portfolio, scenario, config = load_named_inputs(ROOT/'config/illustrative_study.json')
        self.assertEqual(list(portfolio), ['JPM','PNC','GS'])
        self.assertEqual(portfolio['PNC']['pricing_vol'], .28)
        self.assertEqual(scenario['correlations']['JPM','GS'], .70)
        self.assertEqual(len(scenario['correlations']), 3)
        self.assertEqual(config['n_paths'], 5000)
        self.assertEqual(len(config['shared_input_source']['sha256']), 64)

    def test_selection_uses_upper_budget_not_just_point_cost(self):
        table = pd.DataFrame([
            dict(policy='cheap',loss_es95=20.,mean_financed_cost=8.,cost_mean_upper=9.),
            dict(policy='noisy',loss_es95=1.,mean_financed_cost=9.,cost_mean_upper=12.),
        ])
        self.assertEqual(select_policy(table,10),'cheap')
        with self.assertRaises(ValueError): select_policy(table,1)

    def test_selection_tie_break_is_deterministic(self):
        table = pd.DataFrame([
            dict(policy='z',loss_es95=10.,mean_financed_cost=8.,cost_mean_upper=9.),
            dict(policy='a',loss_es95=10.,mean_financed_cost=8.,cost_mean_upper=9.),
        ])
        self.assertEqual(select_policy(table,10),'a')
        self.assertEqual(select_policy(table.iloc[::-1],10),'a')

    def _small_protocol(self, temp):
        data=json.loads(PROTOCOL.read_text())
        data['study_file']=str(ROOT/'config/illustrative_study.json')
        data['selection']['n_paths']=64
        data['evaluation']['n_paths']=96
        data['bootstrap']['n_resamples']=20
        data['candidates']=data['candidates'][:4]+data['candidates'][-2:]
        path=Path(temp)/'protocol.json'
        path.write_text(json.dumps(data))
        return path

    def test_protocol_rejects_same_sample_and_tail_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            path=self._small_protocol(temp)
            spec=json.loads(path.read_text())
            spec['evaluation']['seed']=spec['selection']['seed']
            path.write_text(json.dumps(spec))
            with self.assertRaises(ValueError): load_protocol(path)
            spec['evaluation']['seed']+=1
            spec['tail_probability']=.1
            path.write_text(json.dumps(spec))
            with self.assertRaises(ValueError): load_protocol(path)

    def test_lock_precedes_evaluation_and_report_precedes_complete_marker(self):
        import hedging_harness.research as research
        with tempfile.TemporaryDirectory() as temp:
            protocol=self._small_protocol(temp)
            output=Path(temp)/'run'
            original=research._run_sample
            seen=[]
            def checked(*args,**kwargs):
                label=args[-1]
                if label=='evaluation':
                    self.assertTrue((output/'selection.json').is_file())
                    self.assertFalse((output/'gate_status.json').exists())
                    seen.append(json.loads((output/'selection.json').read_text())['selected_policy'])
                return original(*args,**kwargs)
            def figures(folder,*args):
                (folder/'cost_risk.png').write_bytes(b'test figure')
                (folder/'peak_funding.png').write_bytes(b'test figure')
            with patch.object(research,'_run_sample',side_effect=checked), patch.object(research,'_plots',side_effect=figures):
                result=run_release(protocol,output)
            self.assertEqual(seen,[result['selected_policy']])
            self.assertTrue((output/'report.md').is_file())
            self.assertEqual(json.loads((output/'gate_status.json').read_text())['status'],'complete')
            with self.assertRaises(FileExistsError):run_release(protocol,output)

    def test_render_failure_does_not_leave_false_complete_gate(self):
        import hedging_harness.research as research
        with tempfile.TemporaryDirectory() as temp:
            protocol=self._small_protocol(temp)
            output=Path(temp)/'run'
            with patch.object(research,'_plots',side_effect=RuntimeError('render failed')):
                with self.assertRaises(RuntimeError): run_release(protocol,output)
            self.assertFalse((output/'gate_status.json').exists())
            self.assertTrue((output/'selection.json').is_file())


if __name__=='__main__':unittest.main()

"""Previously unsupported attempts become eligible only after an exact save match."""
import tempfile
import unittest
from pathlib import Path
from records.app import Engine,read_json,write_json


class ChileCatalogueTests(unittest.TestCase):
    def recover(self,stage='SandoChlBioFull',started=True):
        with tempfile.TemporaryDirectory() as directory:
            data=Path(directory)
            (data/'captures').mkdir();(data/'save-reports').mkdir()
            write_json(data/'save-reports/before.json',{'source_sha256':'a'*64,'results':[]})
            attempt={'capture_status':'closed','start_observed':started,'raw_time_ms':10000,
                     'identity':['TestCar','Chile','Test pilot'],'stage_game_id':stage,
                     'result_status':'unsupported_stage','baseline_report_file':'before.json',
                     'trace_file':'attempt.jsonl','started_utc':'2026-11-24T00:00:00+00:00'}
            path=data/'captures/attempt.json';write_json(path,attempt)
            engine=Engine(data,monitor=False)
            engine.report={'source_sha256':'b'*64,'results':[{'mode':'DefaultFreePractice',
                'stage_id':stage,'started_utc':'2026-11-24T00:00:00+00:00','runs':[
                {'index':1,'car':'TestCar','raw_time_ms':10000,'penalty_ms':2000,'official_time_ms':12000}]}]}
            engine.reconcile()
            return read_json(path),engine.items

    def test_both_chile_variants_recover_the_official_result(self):
        for stage in ('SandoChlBioFull','SandoChlBioRevFull'):
            result,items=self.recover(stage)
            self.assertEqual(result['official_time_ms'],12000)
            self.assertEqual(result['penalty_ms'],2000)
            self.assertNotEqual(result.get('result_status'),'unsupported_stage')
            self.assertTrue(items[0]['can_publish'])

    def test_unknown_stage_stays_unsupported(self):
        result,items=self.recover('SandoOtherFull')
        self.assertEqual(result['result_status'],'unsupported_stage')
        self.assertEqual(items,[])

    def test_partial_capture_still_cannot_be_published(self):
        _,items=self.recover(started=False)
        self.assertFalse(items[0]['can_publish'])


if __name__=='__main__':unittest.main()

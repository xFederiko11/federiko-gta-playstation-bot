import copy,unittest
from photo_discovery_v1 import discover,snapshot,report,API,RAW,INPUTS

def sample():
    ids=["registrare-auto-personale","scansionare-veicoli","studiare-animali"]+["sample-"+str(i) for i in range(8)]
    asset=lambda subject,digest:{"subject":subject,"title":subject+" 01","sha256":digest*64,"credit":"Rockstar Games","width":3840,"height":2160}
    return {"guides":{"guides":[{"id":gid} for gid in ids]},"visual_guides":{"guides":[]},
            "requests":{"guides":{gid:["Ruolo fotografico "+str(i) for i in range(5)] for gid in ids}},
            "approved":{"schema":"gta6-approved-screenshots-v4","photos":[]},
            "archive":{"asset_count":3,"assets":[asset("Grotti Cheetah","a"),asset("Rideout Customs","b"),asset("Leonida Keys","c")]},
            "vehicles":{"items":[{"name":"Grotti Cheetah","status":"Verificata","spoiler":False},
                                 {"name":"Grotti Itali RSX","status":"Verificata","spoiler":False}]},
            "references":{"guides":{"scansionare-veicoli":{"1":{"source":"https://www.powerpyx.com/guide/"},
                                      "2":{"source":"https://www.powerpyx.com.evil.test/guide/"}}}},
            "provenance":{"leads":[]}}

class PhotoDiscoveryTests(unittest.TestCase):
    def test_candidates_never_become_approval_and_no_model_substitution(self):
        d=sample();before=copy.deepcopy(d);result=discover(d)
        self.assertEqual(result["unrecorded_roles"],55)
        self.assertEqual([x["model"] for x in result["exact_model_leads"]],["Grotti Cheetah"])
        self.assertEqual(len(result["context_leads"]),3)
        self.assertEqual(len(result["source_references"]),1)
        self.assertEqual(result["new_approvals"],0)
        self.assertEqual(result["downloaded_images"],0)
        self.assertEqual(result["posts"],0)
        self.assertEqual(before,d)
        self.assertIn("non verifica del deploy",report(result,"a"*40))
    def test_fixed_commit_snapshot(self):
        d=sample();calls=[]
        def read(url):
            calls.append(url)
            if url==API:return {"sha":"a"*40}
            return d[next(key for key,path in INPUTS.items() if url==RAW+"a"*40+"/"+path)]
        revision,value=snapshot(read)
        self.assertEqual(revision,"a"*40);self.assertEqual(d,value)
        self.assertEqual(len(calls),1+len(INPUTS))
        with self.assertRaises(ValueError):snapshot(lambda url:{"sha":"../../unsafe"})
    def test_duplicate_hash_or_changed_schema_holds(self):
        d=sample();d["archive"]["assets"][1]["sha256"]="a"*64
        with self.assertRaises(ValueError):discover(d)
        d=sample();d["requests"]["guides"].pop("sample-0")
        with self.assertRaises(ValueError):discover(d)
if __name__=="__main__":unittest.main()

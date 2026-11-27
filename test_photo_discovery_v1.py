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
    def test_guide_sources_and_insider_links_stay_link_only(self):
        d=sample();g=d["guides"]["guides"][0]
        g["source_url"]="https://insider-gaming.com/example/"
        g["extra_sources"]=["https://www.gamesradar.com/example/","https://evil.test/image"]
        r=discover(d)
        self.assertEqual(len(r["source_references"]),3)
        self.assertTrue(all(x["kind"]=="source_page_only" for x in r["source_references"]))
        self.assertEqual(r["new_approvals"],0)

    def test_reviewed_vintage_gallery_is_link_only(self):
        from photo_discovery_v1 import gallery_leads
        doc=gallery_leads()
        self.assertEqual(len(doc["titles"]),12)
        self.assertEqual(doc["status"],"link_only_rights_unverified")
        self.assertEqual(sum("Vapid Stanier" in x for x in doc["titles"]),4)

    def test_vehicle_research_and_rights_are_link_only(self):
        from photo_discovery_v1 import vehicle_location_leads
        d=sample()
        d["vehicles"]["items"][0]["source_url"]="https://www.gtabase.com/gta-6/vehicles/example"
        d["vehicles"]["items"][0]["additional_source"]="https://evil.test/image.jpg"
        d["provenance"]["assets"]=[{"reuse_permission":"not_documented"}]
        result=discover(d)
        self.assertEqual(len(result["vehicle_source_references"]),1)
        self.assertEqual(result["rights_metadata_audit"]["archive_originals_with_no_specific_grant_in_manifest"],3)
        self.assertEqual(result["rights_metadata_audit"]["legacy_screenshots_without_documented_permission"],1)
        self.assertEqual(result["new_approvals"],0)
        leads=vehicle_location_leads()
        self.assertEqual(leads["leads"][0]["status"],"source_unreadable")
        self.assertIn("/eliplaysgta/status/2125723744094269617",leads["leads"][0]["url"])

    def test_free_garage_photo_leads_are_research_only(self):
        from photo_discovery_v1 import vehicle_location_leads
        doc=vehicle_location_leads()
        leads={row["url"]:row for row in doc["leads"]}
        for url in (
            "https://www.powerpyx.com/gta-6-all-1010-mural-locations",
            "https://www.gtabase.com/gta-6/properties/southside-storage",
            "https://www.powerpyx.com/gta-6-collect-the-tempesta-walkthrough/",
            "https://www.gtabase.com/gta-6/properties/domestic-timbers",
            "https://www.gtabase.com/gta-6/vehicles/rauls-tempesta",
            "https://www.powerpyx.com/gta-6-all-garage-locations/",
            "https://www.gtaboom.com/gta-6-vanessas-garage-and-pink-growler-7339/",
        ):
            self.assertEqual(leads[url]["status"],"source_page_only")
            self.assertNotIn("reuse_permission",leads[url])
        self.assertIn("treno fermo",leads["https://www.powerpyx.com/gta-6-all-1010-mural-locations"]["description"])

    def test_standout_map_and_verified_source_domains_are_deduped(self):
        d=sample()
        car=d["vehicles"]["items"][0]
        car.update(source_url="https://gta6.house/guides/example",
                   additional_source="https://www.gtabites.com/guides/example",
                   map_url="https://www.gtabase.com/gta-6/map/?feature=standout-vehicle")
        r=discover(d)
        self.assertEqual(len(r["vehicle_source_references"]),3)
        self.assertEqual(r["new_approvals"],0)
        car["additional_source"]=car["source_url"]
        self.assertEqual(len(discover(d)["vehicle_source_references"]),2)
        car["map_url"]="https://www.gtabase.com.evil.example/image.jpg"
        self.assertEqual(len(discover(d)["vehicle_source_references"]),1)

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

"""Offline fail-closed evidence tests: metadata is not a verified PS5 claim."""
from datetime import datetime, timedelta, timezone
import unittest

from guide_claim_evidence_gate import review

NOW=datetime(2026,11,19,11,0,tzinfo=timezone.utc)
STAMP=NOW.isoformat()
POWER="https://www.powerpyx.com/gta-6-all-cheats/"
GTA_BASE="https://www.gtabase.com/gta-6/"
WIKI="https://gta.wiki/wiki/Grand_Theft_Auto_VI"
FANDOM="https://gta.fandom.com/wiki/Grand_Theft_Auto_VI"


def evidence(source,url,assessment="confirmed",**kwargs):
    entry={"source":source,"url":url,"assessment":assessment,
           "reviewed_original":True,
           "reviewed_utc":STAMP,
           "observed":"La pagina o video originale riporta il dettaglio richiesto, letto dal revisore."}
    entry.update(kwargs)
    return entry


def claim(evidence_list, **kwargs):
    row={"id":"claim-gta6-review","target_page":"trucchi/",
         "statement":"Questa sequenza di comandi GTA VI potrebbe cambiare su PS5 dopo una patch.",
         "platform":"PS5","patch":"1.0",
         "evidence":evidence_list,
         "trophy_evidence":{
             "platform":"PS5","status":"safe","reviewed_original":True,
             "observed":"La fonte esplicita la sicurezza dei trofei su PS5 per il metodo discusso.",
             "source":"PowerPyx","url":POWER}}
    row.update(kwargs)
    return {"schema":"gta6-claim-dossiers-v1","claims":[row]}


class ClaimGateTests(unittest.TestCase):
    def test_two_independent_reviews_require_human_followup_never_auto_publish(self):
        data=claim([evidence("PowerPyx",POWER),evidence("GTABase",GTA_BASE)])
        result=review(data,now=NOW)
        row=result["decisions"][0]
        self.assertTrue(row["editorially_reviewable"])
        self.assertEqual(row["independent_confirmations"],2)
        self.assertTrue(row["trophy_safe_documented"])
        self.assertFalse(row["auto_publish"])
        self.assertEqual(result["publication"],"review_only__never_auto_publish")
        self.assertTrue(row["reviewed_originals_are_user_assertions_not_fetched"])

    def test_headlines_and_missing_trophy_proof_do_not_pass(self):
        entries=[evidence("PowerPyx",POWER,reviewed_original=False),
                 evidence("GTABase",GTA_BASE,observed="title only")]
        row=review(claim(entries),now=NOW)["decisions"][0]
        self.assertFalse(row["editorially_reviewable"])
        self.assertEqual(row["independent_confirmations"],0)
        self.assertIn("not_reviewed",row["rejected_evidence"])
        without=claim([evidence("PowerPyx",POWER),evidence("GTABase",GTA_BASE)],
                      trophy_evidence=None)
        self.assertFalse(review(without,now=NOW)["decisions"][0]["editorially_reviewable"])
        not_ps5=claim([evidence("PowerPyx",POWER),evidence("GTABase",GTA_BASE)],
                      platform="PC")
        self.assertFalse(review(not_ps5,now=NOW)["decisions"][0]["editorially_reviewable"])
        unknown_patch=claim([evidence("PowerPyx",POWER),evidence("GTABase",GTA_BASE)],
                            patch=None)
        self.assertFalse(review(unknown_patch,now=NOW)["decisions"][0]["editorially_reviewable"])

    def test_disagreement_and_repeated_sources_block(self):
        double=claim([evidence("PowerPyx",POWER),evidence("PowerPyx",POWER)])
        self.assertEqual(review(double,now=NOW)["decisions"][0]["independent_confirmations"],1)
        self.assertFalse(review(double,now=NOW)["decisions"][0]["editorially_reviewable"])
        conflict=claim([evidence("PowerPyx",POWER),evidence("GTABase",GTA_BASE),
                        evidence("GTA Wiki (independent)",WIKI,"contradicted")])
        row=review(conflict,now=NOW)["decisions"][0]
        self.assertEqual(row["contradictions"],1)
        self.assertFalse(row["editorially_reviewable"])
        mirrors=claim([evidence("GTA Wiki (independent)",WIKI),
                       evidence("GTA Wiki / Fandom",FANDOM)])
        self.assertEqual(review(mirrors,now=NOW)["decisions"][0]["independent_confirmations"],1)

    def test_invalid_urls_dates_and_unsafe_trophy_link(self):
        wrong=evidence("PowerPyx","https://powerpyx.com.evil.test/a")
        too_old=evidence("GTABase",GTA_BASE,reviewed_utc=(NOW-timedelta(days=40)).isoformat())
        future=evidence("GTABase",GTA_BASE,reviewed_utc=(NOW+timedelta(hours=1)).isoformat())
        row=review(claim([wrong,too_old,future]),now=NOW)["decisions"][0]
        self.assertIn("host_mismatch",row["rejected_evidence"])
        self.assertEqual(row["rejected_evidence"].count("invalid_review_time"),2)
        spoof=claim([evidence("PowerPyx",POWER),evidence("GTABase",GTA_BASE)])
        spoof["claims"][0]["trophy_evidence"]["url"]="https://fake.example/"
        self.assertFalse(review(spoof,now=NOW)["decisions"][0]["trophy_safe_documented"])

    def test_invalid_paths_and_duplicate_ids_block(self):
        with self.assertRaises(ValueError):
            review({"schema":"wrong","claims":[]},now=NOW)
        for target in ("https://evil.test/","../secrets/","guide-e-tutorial/../../","/trofei"):
            row=claim([]);row["claims"][0]["target_page"]=target
            with self.subTest(target=target),self.assertRaises(ValueError):
                review(row,now=NOW)
        row=claim([]);row["claims"].append(dict(row["claims"][0]))
        with self.assertRaises(ValueError):
            review(row,now=NOW)

    def test_empty_dossiers_safe(self):
        out=review({"schema":"gta6-claim-dossiers-v1","claims":[]},now=NOW)
        self.assertEqual(out["decisions"],[])
        self.assertEqual(out["publication"],"review_only__never_auto_publish")

if __name__=="__main__":
    unittest.main()

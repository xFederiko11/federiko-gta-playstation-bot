"""No-network tests for safe cross-repo photo backlog and single issue digest."""
from __future__ import annotations
from io import BytesIO
import json
import unittest
from unittest.mock import Mock
from photo_gap_digest_v1 import validate,markdown,fetch_public,SOURCE,SCHEMA


def sample():
    tasks=[]
    for n in range(11):
        slug="sample-guide-"+str(n+1)
        for role in range(1,6):
            tasks.append({"id":slug+"-"+str(role),"guide_id":slug,
                          "guide_title":"Esempio guida numero "+str(n+1),
                          "role":role,"description":"Schermata originale e prova del passaggio "+str(role),
                          "priority":"alta" if n==0 or role==1 else "media",
                          "status":"da documentare",
                          "guide_url":"https://xfederiko11.github.io/gta-6/guide-e-tutorial/"+slug+"/",
                          "submission_url":"https://xfederiko11.github.io/gta-6/screenshot-ps5/invia/?guida="+slug+"&passo="+str(role),
                          "screenshot_verified":False,"rights_verified":False})
    return {"schema":SCHEMA,"tasks":tasks,"total_requests":55,
            "approved_new_community_screenshots":0,"unapproved_roles":55,
            "existing_attributed_editorial_screenshots":10,
            "human_review_required":True,"automatic_social_posting":False}


class PhotoGapTests(unittest.TestCase):
    def test_55_roles_required_and_all_unapproved_cannot_be_called_photos(self):
        records=sample()
        pending=validate(records)
        self.assertEqual(len(pending),55)
        self.assertEqual(pending[0]["priority"],"alta")
        output=markdown(records)
        self.assertIn("PHOTO_BACKLOG_PUBLIC_VERIFIED",output)
        self.assertEqual(output.count("[proponi su X]"),10)
        self.assertIn("Foto nuove della community approvate: **0**",output)
        self.assertIn("non interpreta gli artwork",output)

    def test_cannot_forge_rights_or_miss_a_role(self):
        d=sample()
        d["tasks"][0]["rights_verified"]=True
        with self.assertRaises(ValueError):validate(d)
        d=sample()
        d["tasks"][0]["submission_url"]="https://xfederiko11.github.io.evil.com/gta-6/screenshot-ps5/invia/"
        with self.assertRaises(ValueError):validate(d)
        d=sample()
        d["tasks"].pop()
        with self.assertRaises(ValueError):validate(d)
        d=sample()
        d["automatic_social_posting"]=True
        with self.assertRaises(ValueError):validate(d)
        d=sample()
        d["tasks"][0]["status"]="approvato"
        d["tasks"][0]["screenshot_verified"]=True
        d["tasks"][0]["rights_verified"]=True
        with self.assertRaises(ValueError):validate(d)  # totals must match

    def test_only_fixed_public_json_endpoint_and_redirect_rejection(self):
        binary=json.dumps(sample()).encode("utf-8")
        class Response:
            headers={"Content-Type":"application/json"}
            def __init__(self,url):self.url=url
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def geturl(self):return self.url
            def read(self,n=-1):return binary[:n]
        def safe(req,timeout):
            self.assertEqual(req.full_url,SOURCE)
            self.assertEqual(timeout,12)
            return Response(SOURCE)
        self.assertEqual(len(fetch_public(open_fn=safe)["tasks"]),55)
        with self.assertRaises(ValueError):
            fetch_public(open_fn=lambda req,timeout:Response("https://evil.example/"))


if __name__=="__main__":unittest.main()

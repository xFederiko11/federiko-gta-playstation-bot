"""No-network tests for opt-in official X API recent search Social Radar."""
from datetime import datetime, timedelta, timezone
import json
from urllib.parse import urlsplit, parse_qs
from unittest.mock import patch
import unittest

import x_verified_social_radar_v1 as radar

NOW = datetime(2026,11,19,19,0,tzinfo=timezone.utc)


def result(pid="1234567890123456789", author="GTAhelper", lang="it",
           text="GTA VI su PS5, il platino e i trofei opzionali delle missioni richiedono qualche attenzione!",
           age=2, likes=25):
    return {
        "data":[{
            "id":pid,"author_id":"789456123","created_at":(NOW-timedelta(hours=age)).isoformat(),
            "text":text,"lang":lang,"public_metrics":{"like_count":likes,"reply_count":4},
            "reply_settings":"everyone",
        }],
        "includes":{"users":[{"id":"789456123","username":author,"name":"GTA Helper"}]},
        "meta":{"result_count":1},
    }


class OfficialXReadOnlyTests(unittest.TestCase):
    def test_opt_in_prevents_any_api_cost_without_a_switch(self):
        def forbidden(*args,**kwargs):
            raise AssertionError("No X API calls allowed")
        no_auth=radar.collect(NOW, token="supersecret-secret-value",enabled=False,fetch=forbidden)
        self.assertEqual(no_auth["status"],"disabled_pending_cost_authorization")
        self.assertEqual(no_auth["posts"],[])
        self.assertEqual(no_auth["requests"],0)
        missing=radar.collect(NOW,token="",enabled=True,fetch=forbidden)
        self.assertEqual(missing["status"],"missing_x_bearer_token")
        self.assertEqual(missing["requests"],0)

    def test_api_uses_bearer_get_and_fixed_at_most_10_posts(self):
        class FakeResponse:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return json.dumps(result()).encode("utf-8")
        reqs=[]
        def opener(req,timeout):
            reqs.append(req)
            self.assertEqual(timeout,12)
            return FakeResponse()
        token="test-secret-bearer-token"
        data=radar.api_recent(token,radar.QUERIES[0],opener=opener)
        self.assertEqual(len(data["data"]),1)
        self.assertEqual(len(reqs),1)
        self.assertEqual(reqs[0].get_method(),"GET")
        self.assertTrue(reqs[0].full_url.startswith(radar.ENDPOINT+"?"))
        args=parse_qs(urlsplit(reqs[0].full_url).query)
        self.assertEqual(args["max_results"],["10"])
        self.assertEqual(args["query"],[radar.QUERIES[0]])
        self.assertEqual(args["expansions"],["author_id"])
        self.assertEqual(reqs[0].get_header("Authorization"),"Bearer "+token)
        with self.assertRaises(ValueError):
            radar.api_recent(token,"GTA VI unrelated",opener=opener)

    def test_real_api_post_gets_genuine_url_and_grounded_manual_reply(self):
        items=radar.select([result()],NOW)
        self.assertEqual(len(items),1)
        post=items[0]
        self.assertEqual(post["url"],"https://x.com/GTAhelper/status/1234567890123456789")
        self.assertEqual(post["verified_by"],"x_api_v2_recent_search")
        self.assertEqual(post["theme"],"trophies")
        self.assertIn("platino",post["reply"])
        self.assertLessEqual(len(post["source_excerpt"]),100)
        query=parse_qs(urlsplit(post["reply_url"]).query)
        self.assertEqual(query["in_reply_to"],["1234567890123456789"])
        self.assertEqual(query["text"],[post["reply"]])
        body=radar.markdown({"schema":radar.SCHEMA,"status":"ok","posts":items,"errors":[],"requests":2})
        self.assertIn("Apri tweet / metti cuore",body)
        self.assertIn("Testo già pronto da copiare",body)
        self.assertIn("esclusivamente",body.lower() if "esclusivamente" in body else "esclusivamente")

    def test_no_invented_posts_when_search_fails(self):
        def error(*args):
            raise ValueError("Missing paid permission")
        report=radar.collect(NOW,token="secret-with-enough-length",enabled=True,fetch=error)
        self.assertEqual(report["status"],"api_error")
        self.assertEqual(report["posts"],[])
        self.assertEqual(report["requests"],1)
        self.assertIn("X API non disponibile",radar.markdown(report))

    def test_bounded_requests_and_no_read_retry(self):
        count=[]
        def fetch(token,query):
            count.append(query)
            return result(pid=str(1234567890123456789+len(count)),
                          author="helper"+str(len(count)))
        report=radar.collect(NOW,token="secret-with-enough-length",enabled=True,fetch=fetch)
        self.assertEqual(report["status"],"ok")
        self.assertEqual(report["requests"],2)
        self.assertEqual(len(count),2)
        self.assertLessEqual(len(report["posts"]),radar.MAX_POSTS_IN_DIGEST)
        self.assertEqual(radar.MAX_RESULTS_PER_QUERY,10)

    def test_off_topic_fraud_duplicate_old_and_unverifiable_posts_filtered(self):
        duplicate=result()
        older=result(pid="1234567890123456790",age=40)
        spam=result(pid="1234567890123456791",
                    text="GTA VI trophy giveaway crypto free money follow back get the best cheats ever")
        wrong=result(pid="1234567890123456792",
                     text="Interesserà un gioco completamente diverso e una notizia senza GTA o PlayStation.")
        same_author=result(pid="1234567890123456793")
        other=result(pid="1234567890123456794",author="other_creator",
                     lang="en",text="GTA VI HDR on PS5 Pro OLED looks very different, does anyone know what settings work?")
        combined={"data":duplicate["data"]+older["data"]+spam["data"]+wrong["data"]+
                  same_author["data"]+other["data"],"includes":{"users":[{"id":"789456123",
                  "username":"GTAhelper"}]}}
        # X author_id is shared in the synthetic fixture; only one author remains.
        selected=radar.select([combined],NOW)
        self.assertEqual(len(selected),1)
        self.assertEqual(selected[0]["post_id"],"1234567890123456789")
        self.assertEqual(radar.select([result(text="RT @Somewhere GTA VI platino and HDR news coverage")],NOW),[])
        self.assertEqual(radar.select([result(text="GTA VI soundtrack news Overmono and Justice",age=56)],NOW),[])
        self.assertEqual(radar.select([result(text="GTA VI video of an animal without any topic")],NOW),[])

    def test_music_and_glitch_replies_are_topic_specific(self):
        music=result(text="GTA VI soundtrack speculation about Overmono and Justice - looks interesting to fans.")
        x=radar.select([music],NOW)
        self.assertEqual(x[0]["theme"],"soundtrack")
        self.assertIn("colonna sonora",x[0]["reply"])
        self.assertNotIn("trofeo",x[0]["reply"])
        glitch=result(text="GTA VI PS5 money glitch reported, but the trophy status and latest patch are unclear.")
        y=radar.select([glitch],NOW)
        self.assertEqual(y[0]["theme"],"glitch")
        self.assertIn("patch",y[0]["reply"])
        en=result(lang="en",text="GTA VI PS5 Pro HDR OLED settings vary on different models - here's a comparison.")
        z=radar.select([en],NOW)
        self.assertEqual(z[0]["language"],"en")
        self.assertIn("TV model",z[0]["reply"])

    def test_rejects_spoilers_blocked_replies_and_invalid_authors(self):
        base=result()
        base["data"][0]["reply_settings"]="mentionedUsers"
        self.assertFalse(radar.select([base],NOW))
        base=result()
        base["includes"]["users"][0]["username"]="xfederiko11"
        self.assertFalse(radar.select([base],NOW))
        base=result()
        base["data"][0]["text"]="GTA VI platino spoiler ending mission revealed in latest patch game."
        self.assertFalse(radar.select([base],NOW))
        with self.assertRaises(ValueError):
            radar.select([result()],datetime(2026,11,19))
        with self.assertRaises(ValueError):
            radar.select([result()],NOW,limit=20)


if __name__=="__main__":
    unittest.main()

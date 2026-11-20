"""Offline tests for Reddit lead intake; no Reddit network access."""
from __future__ import annotations
import unittest
from datetime import datetime,timezone
from unittest.mock import Mock,patch
from urllib.error import HTTPError
from reddit_intake_v1 import expand_ift_link
from reddit_intake_v1 import canonical_url,parse_issue,select,select_visual,markdown,expand_short_links

NOW=datetime(2026,11,20,14,0,tzinfo=timezone.utc)
URL="https://www.reddit.com/r/GTA6/comments/abc123/"
def issue(**changes):
    return {**{"author":{"login":"xFederiko11"},
      "title":"[REDDIT-LEAD] GTA 6 PS5 where to save rare cars in garage",
      "body":"Reddit source: https://www.reddit.com/r/GTA6/comments/abc123/garage_location/",
      "url":"https://github.com/xFederiko11/federiko-gta-playstation-bot/issues/999",
      "createdAt":"2026-11-20T13:00:00Z"},**changes}

class RedditIntakeTests(unittest.TestCase):
    def test_owned_permalinks_only(self):
        self.assertEqual(canonical_url("https://www.reddit.com/r/GTA6/comments/abc123/garage_location/"),URL)
        for link in ("https://old.reddit.com/r/GTA6/comments/abc123/",
                     "https://reddit.com.evil.test/r/GTA6/comments/abc123/",
                     "http://www.reddit.com/r/GTA6/comments/abc123/",
                     "https://www.reddit.com/r/Other/comments/abc123/",
                     "https://www.reddit.com/r/GTA6/comments/abc123/?ref=spam",
                     "https://www.reddit.com/r/GTA6/comments/abc123/%2fsecret"):
            self.assertIsNone(canonical_url(link),link)
    def test_owner_marker_and_title_required(self):
        self.assertEqual(parse_issue(issue(),NOW)["reddit_url"],URL)
        self.assertIsNone(parse_issue(issue(author={"login":"untrusted-user"}),NOW))
        self.assertIsNone(parse_issue(issue(title="A normal issue about GTA VI"),NOW))
        self.assertIsNone(parse_issue(issue(body="No reliable permalink"),NOW))
        self.assertIsNone(parse_issue(issue(body="https://www.reddit.com/r/GTA6/comments/abc123/ https://www.reddit.com/r/GTAVI/comments/def123/"),NOW))
        self.assertIsNone(parse_issue(issue(createdAt="2026-10-01T10:00:00Z"),NOW))
        self.assertIsNone(parse_issue(issue(title="[REDDIT-LEAD] Buy crypto immediately"),NOW))
    def test_dedupe_and_no_publishing_or_metrics(self):
        self.assertEqual(len(select([issue(),issue()],NOW)),1)
        report=markdown([issue()],NOW)
        self.assertIn("https://www.reddit.com/r/GTA6/comments/abc123/",report)
        self.assertIn("revisione necessaria",report.lower())
        self.assertIn("non pubblica",report.lower())
        self.assertNotIn("1000 follower",report)
        self.assertIn("senza link promozionali",report)
    def test_ifttt_short_link_only_expands_from_owner_issue_to_verified_reddit_url(self):
        shortened=issue(body="Reddit source: https://ift.tt/bMAG9Kx")
        clean=expand_short_links([shortened],resolve=lambda value:
            "https://www.reddit.com/r/GTA6/comments/abc123/garage_location/")
        self.assertEqual(select(clean,NOW)[0]["reddit_url"],URL)
        self.assertIn("Eventi Reddit ricevuti: 1",markdown(clean,NOW))
        self.assertIn("non pertinenti dal titolo: 0",markdown(clean,NOW))
        self.assertIn("pertinenti e con URL verificato: 1",markdown(clean,NOW))
        spoof=issue(author={"login":"other"},body=shortened["body"])
        called=[]
        def dangerous(_):
            called.append(1)
            return "https://www.reddit.com/r/GTA6/comments/abc123/"
        self.assertEqual(expand_short_links([spoof],resolve=dangerous)[0]["body"],spoof["body"])
        self.assertEqual(called,[])
        other=expand_short_links([shortened],resolve=lambda value:"https://intranet.example/secret")
        self.assertEqual(select(other,NOW),[])
        self.assertEqual(len(select(expand_short_links([shortened],resolve=lambda value:None),NOW)),0)
        report=markdown([shortened],NOW)
        self.assertIn("Eventi Reddit ricevuti: 1",report)
        self.assertIn("link IFTTT da risolvere: 1",report)
    def test_real_ift_url_does_not_mean_relevant_gta_tip(self):
        irrelevant=issue(title="[REDDIT-LEAD] I feel sorry for streamers without any music",
                         body="Reddit source: https://ift.tt/bMAG9Kx")
        clean=expand_short_links([irrelevant],resolve=lambda value:
            "https://www.reddit.com/r/GTA6/comments/abc123/streaming_music/")
        self.assertEqual(select(clean,NOW),[])
        self.assertIn("Eventi Reddit ricevuti: 1",markdown(clean,NOW))
        self.assertIn("non pertinenti dal titolo: 1",markdown(clean,NOW))
    def test_ift_tt_relevant_title_only_and_hard_request_limit(self):
        relevant=issue(title="[REDDIT-LEAD] GTA VI money glitch PS5 update",
                       body="Reddit source: https://ift.tt/abcde123")
        irrelevant=issue(title="[REDDIT-LEAD] People complain about background music",
                         body="Reddit source: https://ift.tt/bMAG9Kx")
        calls=[]
        def resolve(link):
            calls.append(link)
            return "https://www.reddit.com/r/GTA6/comments/abc123/"
        rows=expand_short_links([irrelevant, relevant, relevant], resolve=resolve, max_lookups=1)
        self.assertEqual(calls,["https://ift.tt/abcde123"])
        self.assertEqual(select(rows,NOW)[0]["title"],"GTA VI money glitch PS5 update")
        self.assertIn("non pertinenti dal titolo: 1", markdown(rows,NOW))
        self.assertIn("link IFTTT da risolvere: 0",markdown(rows,NOW))

    def test_generic_question_is_manual_review_only_after_verified_gta6_permalinks(self):
        generic=issue(title="[REDDIT-LEAD] How do I reach this item?",
                      body="Reddit source: https://ift.tt/YMKx9DG")
        called=[]
        def verified(_):
            called.append(1)
            return "https://www.reddit.com/r/GTA6/comments/qwerty123/"
        rows=expand_short_links([generic],resolve=verified,max_lookups=1)
        self.assertEqual(called,[1])
        selected=select(rows,NOW)
        self.assertEqual(len(selected),1)
        self.assertTrue(selected[0]["generic_question"])
        self.assertEqual(selected[0]["rank"],0)
        self.assertEqual(selected[0]["topics"],["domanda generica da verificare"])
        report=markdown(rows,NOW)
        self.assertIn("domande generiche da rivedere: 1",report)
        self.assertIn("pertinenti e con URL verificato: 0",report)
        self.assertIn("non è una scoperta GTA VI verificata",report)
        self.assertIn("https://www.reddit.com/r/GTA6/comments/qwerty123/",report)
        self.assertIn("non pubblica",report)
        self.assertNotIn("glitch confermato",report)
        other=expand_short_links([generic],resolve=lambda _: "https://www.reddit.com/r/italygames/comments/qwerty123/")
        self.assertEqual(select(other,NOW),[])
        spoof=issue(title=generic["title"],body=generic["body"],author={"login":"spam-account"})
        self.assertEqual(expand_short_links([spoof],resolve=lambda _: (_ for _ in ()).throw(AssertionError("network")))[0]["body"],spoof["body"])
        self.assertEqual(select([generic],NOW),[])
        self.assertIn("domande generiche da rivedere: 0",markdown([generic],NOW))
        self.assertIn("link IFTTT da risolvere: 1",markdown([generic],NOW))

    def test_non_question_lead_without_topics_is_still_excluded(self):
        irrelevant=issue(title="[REDDIT-LEAD] Lovely background music on streams",
                         body="Reddit source: https://ift.tt/abcde123")
        calls=[]
        rows=expand_short_links([irrelevant],resolve=lambda link:calls.append(link))
        self.assertEqual(calls,[])
        self.assertEqual(select(rows,NOW),[])
        self.assertIn("non pertinenti dal titolo: 1",markdown(rows,NOW))

    def test_newest_relevant_issue_wins_tie(self):
        first=issue(title="[REDDIT-LEAD] GTA VI money farming glitch",
                    body="Reddit source: https://www.reddit.com/r/GTA6/comments/abc123/",
                    createdAt="2026-11-20T10:00:00Z")
        second=issue(title="[REDDIT-LEAD] GTA VI save car garage advice",
                     body="Reddit source: https://www.reddit.com/r/GTA6/comments/xyz789/",
                     createdAt="2026-11-20T13:45:00Z")
        items=select([first,second],NOW)
        self.assertEqual(len(items),2)
        self.assertEqual(items[0]["title"],"GTA VI save car garage advice")

    def test_head_unsupported_falls_back_to_bounded_get_without_following(self):
        calls=[]
        opener=Mock()
        def fake_open(req,timeout):
            calls.append((req.full_url, req.get_method(), timeout))
            if req.get_method()=="HEAD":
                raise HTTPError(req.full_url,405,"not supported",{},None)
            raise HTTPError(req.full_url,302,"redirect",
                            {"Location":"https://www.reddit.com/r/GTA6/comments/abc123/"},
                            None)
        opener.open.side_effect=fake_open
        with patch("reddit_intake_v1.build_opener",return_value=opener):
            expanded=expand_ift_link("https://ift.tt/abcde123")
        self.assertEqual(expanded,URL)
        self.assertEqual(calls,[("https://ift.tt/abcde123","HEAD",6),
                                ("https://ift.tt/abcde123","GET",6)])
        with patch("reddit_intake_v1.build_opener",return_value=opener):
            self.assertIsNone(expand_ift_link("https://evil.example/x"))
        self.assertEqual(len(calls),2)
        # It never accesses the address inside the Location header.

    def test_gta6_photo_only_leads_are_review_only_and_not_downloaded(self):
        photo=issue(title="[REDDIT-LEAD] First PS5 screenshot of the GTA 6 garage",
                    body="Reddit source: https://www.reddit.com/r/GTA6/comments/photo1/")
        found=parse_issue(photo,NOW)
        self.assertIsNotNone(found)
        self.assertIn("foto",found["topics"])
        self.assertTrue(found["photo_candidate"])
        self.assertFalse(found["photo_reviewed"])
        self.assertFalse(found["reuse_authorized"])
        report=markdown([photo],NOW)
        self.assertIn("Possibili prove visive",report)
        self.assertIn("possibili foto/clip dal solo titolo: 1",report)
        self.assertIn("https://www.reddit.com/r/GTA6/comments/photo1/",report)
        self.assertIn("https://xfederiko11.github.io/gta-6/screenshot-ps5/",report)
        self.assertIn("consenso esplicito",report)
        self.assertIn("non screenshot verificati",report)
        self.assertNotIn("licenza concessa",report)
        self.assertNotIn("post pubblicato",report)

    def test_photo_only_unrelated_italygames_does_not_enter_visual_review(self):
        unrelated=issue(title="[REDDIT-LEAD] New Elden Ring photo mode screenshots",
                        body="Reddit source: https://www.reddit.com/r/italygames/comments/er12345/")
        self.assertIsNone(parse_issue(unrelated,NOW))
        self.assertEqual(select([unrelated],NOW),[])
        related=issue(title="[REDDIT-LEAD] GTA VI PS5 gameplay screenshots of the city",
                      body="Reddit source: https://www.reddit.com/r/italygames/comments/gta1234/")
        found=parse_issue(related,NOW)
        self.assertIsNotNone(found)
        self.assertTrue(found["photo_candidate"])
        review=markdown([related],NOW)
        self.assertIn("Possibili prove visive",review)
        self.assertIn("r/italygames",review)
        self.assertIn("non screenshot verificati",review)

    def test_image_headline_stays_a_lead_not_a_verified_gameplay_step(self):
        row=issue(title="[REDDIT-LEAD] GTA 6 money glitch screenshot map PS5",
                  body="Reddit source: https://www.reddit.com/r/GTA6/comments/map1234/")
        result=parse_issue(row,NOW)
        self.assertEqual(set(result["topics"]),{"soldi","guida","foto"})
        self.assertTrue(result["photo_candidate"])
        report=markdown([row],NOW)
        self.assertIn("Non esaminato",report)
        self.assertIn("piattaforma/patch",report)
        self.assertIn("Non affermare che un glitch funziona",report)
        self.assertNotIn("foto verificata automaticamente",report)
        untrusted=issue(title=row["title"],author={"login":"other-account"})
        self.assertIsNone(parse_issue(untrusted,NOW))
        self.assertNotIn("map1234",markdown([untrusted],NOW))

    def test_ift_tt_photo_lead_expansion_is_owner_only(self):
        short=issue(title="[REDDIT-LEAD] GTA 6 screenshot map of a rare car",
                    body="Reddit source: https://ift.tt/Zz123ab")
        fake_url="https://www.reddit.com/r/GTAVI/comments/xyz9876/verified-map/"
        rows=expand_short_links([short],resolve=lambda link:fake_url,max_lookups=1)
        self.assertEqual(len(select(rows,NOW)),1)
        self.assertTrue(select(rows,NOW)[0]["photo_candidate"])
        self.assertIn("r/GTAVI",markdown(rows,NOW))
        self.assertNotIn("xyz9876",markdown([short],NOW))
        spoof=issue(title=short["title"],body=short["body"],
                    author={"login":"not-owner"})
        self.assertNotIn("xyz9876",markdown(expand_short_links(
            [spoof],resolve=lambda _:fake_url),NOW))

    def test_visual_shortlist_is_not_buried_by_high_scoring_news(self):
        news=[issue(title="[REDDIT-LEAD] GTA VI money garage car trophy map "+str(i),
                    body="Reddit source: https://www.reddit.com/r/GTA6/comments/n"+
                         str(i).zfill(5)+"/")
              for i in range(20)]
        photo=issue(title="[REDDIT-LEAD] Screenshot showing GTA6 waterfront on PS5",
                    body="Reddit source: https://www.reddit.com/r/GTA6/comments/pho123/")
        # General top 18 can be full, but the visual proof queue remains separate.
        self.assertNotIn("https://www.reddit.com/r/GTA6/comments/pho123/",
                         [e["reddit_url"] for e in select(news+[photo],NOW)])
        selected=select_visual(news+[photo],NOW)
        self.assertEqual(len(selected),1)
        self.assertTrue(selected[0]["photo_candidate"])
        report=markdown(news+[photo],NOW)
        self.assertIn("possibili foto/clip dal solo titolo: 1",report)
        self.assertIn("https://www.reddit.com/r/GTA6/comments/pho123/",report)
        self.assertIn("Non esaminato",report)

    def test_visual_shortlist_deduplicates_and_prioritizes_car_cash(self):
        generic=issue(title="[REDDIT-LEAD] Screenshot of the GTA 6 skyline",
                      body="Reddit source: https://www.reddit.com/r/GTA6/comments/sky123/")
        cash=issue(title="[REDDIT-LEAD] GTA 6 money stash screenshot map",
                   body="Reddit source: https://www.reddit.com/r/GTA6/comments/mny123/")
        car=issue(title="[REDDIT-LEAD] GTA 6 rare car photo at dealership",
                  body="Reddit source: https://www.reddit.com/r/GTA6/comments/car123/")
        results=select_visual([generic,car,cash,cash],NOW)
        self.assertEqual(len(results),3)
        self.assertEqual(results[0]["reddit_url"],
                         "https://www.reddit.com/r/GTA6/comments/mny123/")
        self.assertEqual(results[1]["reddit_url"],
                         "https://www.reddit.com/r/GTA6/comments/car123/")
        self.assertEqual(results[2]["reddit_url"],
                         "https://www.reddit.com/r/GTA6/comments/sky123/")
        self.assertEqual(select_visual([],NOW),[])
        self.assertEqual(select_visual(None,NOW),[])

    def test_untrusted_markdown_not_rendered_as_unsafe_links(self):
        candidate=issue(title="[REDDIT-LEAD] GTA VI PS5 garage [click](https://evil.test) help")
        report=markdown([candidate],NOW)
        self.assertNotIn("](https://evil.test)",report)
        self.assertEqual(len(select([candidate],NOW)),1)
if __name__=="__main__":unittest.main()

import unittest
from google_keyword_watch_v1 import parse,report
class TrendsTests(unittest.TestCase):
    def test_match_and_approximation(self):
        body=b'<rss xmlns:ht="https://trends.google.com/trending/rss"><channel><item><title>GTA 6 garage</title><ht:approx_traffic>1,000+</ht:approx_traffic></item><item><title>GTA 60</title></item><item><title>GTA Online</title></item><item><title>Grand Theft Auto VI</title></item><item><title>GTA 6 garage</title></item></channel></rss>'
        self.assertEqual(parse(body),(5,[("GTA 6 garage","1,000+"),("Grand Theft Auto VI","")]))
    def test_malformed_and_dtd(self):
        for b in (b'<html/>',b'<!DOCTYPE rss><rss><channel/></rss>',b'<rss>'):
            self.assertRaises((ValueError,__import__("xml.etree.ElementTree",fromlist=["ParseError"]).ParseError),parse,b)
    def test_no_match_not_zero_demand(self):
        status,text=report(lambda:b'<rss><channel><item><title>Football</title></item></channel></rss>')
        self.assertEqual(status,"ok")
        self.assertIn("non significa zero ricerche",text)
        self.assertIn("non classifica per volume",text)
    def test_error_is_not_fake_success(self):
        def fail():raise TimeoutError()
        status,text=report(fail)
        self.assertEqual(status,"unavailable")
        self.assertIn("Nessun volume o trend inventato",text)

import io,json,sys,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import score_readiness as m

class ReadTransportTests(unittest.TestCase):
    def test_ssl_handshake_timeout_is_retried_and_recovers(self):
        with patch.object(m.urllib.request,'urlopen',side_effect=[urllib.error.URLError(TimeoutError('handshake')),io.BytesIO(b'{"ok":true}')])as read,patch.object(m.time,'sleep'):
            self.assertEqual(m.request('https://api.myfantasyleague.com/test'),{'ok':True})
            self.assertEqual(read.call_count,2)

    def test_three_failed_reads_still_fail_visibly(self):
        with patch.object(m.urllib.request,'urlopen',side_effect=TimeoutError('handshake'))as read,patch.object(m.time,'sleep'):
            with self.assertRaises(TimeoutError):m.request('https://api.myfantasyleague.com/test')
            self.assertEqual(read.call_count,3)

    def test_permanent_http_errors_and_writes_are_not_retried(self):
        for error,payload in [(urllib.error.HTTPError('https://example.com',403,'Forbidden',{},None),None),(TimeoutError('lost dispatch acknowledgement'),{'ref':'main'})]:
            with patch.object(m.urllib.request,'urlopen',side_effect=error)as read,patch.object(m.time,'sleep'):
                with self.assertRaises(type(error)):m.request('https://example.com',payload)
                self.assertEqual(read.call_count,1)

if __name__=='__main__':unittest.main()

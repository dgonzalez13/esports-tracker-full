import unittest

from bs4 import BeautifulSoup

from web_tracker.player_indicators import decorate_player_names
from web_tracker.generate_site import render_page


def payload():
    return {'leagues': {'GT': [
        {'player': 'Alpha', 'indicator': 'GREEN'},
        {'player': 'Beta', 'indicator': 'RED'},
        {'player': 'Neutral', 'indicator': 'NONE'},
    ]}}


class PlayerIndicatorTests(unittest.TestCase):
    def test_names_everywhere_both_sides_and_existing_markers(self):
        html = ('<h3>Alpha</h3><table><tr><td>GT</td><td>Alpha - Beta</td></tr></table>'
                '<pre>GT Alpha - Beta [1]</pre><p>🟢 Alpha / 🔴 Beta / 🔴 Neutral</p>'
                '<p>Alphabet / Unknown</p>')
        result = BeautifulSoup(decorate_player_names(html, payload()), 'html.parser').get_text()
        self.assertEqual(result.count('🟢 Alpha'), 4)
        self.assertEqual(result.count('🔴 Beta'), 3)
        self.assertNotIn('🟢 🟢', result)
        self.assertNotIn('🔴 Neutral', result)
        self.assertIn('Alphabet / Unknown', result)

    def test_scripts_attributes_comments_and_escaped_names_are_safe(self):
        data = {'leagues': {'GT': [{'player': 'A & B', 'indicator': 'RED'}]}}
        html = '<p title="A &amp; B">A &amp; B</p><script>"A & B"</script><!-- A & B -->'
        soup = BeautifulSoup(decorate_player_names(html, data), 'html.parser')
        self.assertEqual(soup.p.text, '🔴 A & B')
        self.assertEqual(soup.p['title'], 'A & B')
        self.assertEqual(soup.script.string, '"A & B"')

    def test_shared_names_use_league_context(self):
        data = payload()
        data['leagues']['EADRIATIC'] = [{'player': 'Alpha', 'indicator': 'RED'}]
        html = ('<div data-league="GT"><p>Alpha</p></div>'
                '<tr><td>EADRIATIC</td><td>Alpha</td></tr><pre>GT Alpha</pre>')
        result = decorate_player_names(html, data)
        self.assertEqual(result.count('🟢 Alpha'), 2)
        self.assertEqual(result.count('🔴 Alpha'), 1)

    def test_page_upcoming_and_streaks_use_same_indicators(self):
        data = payload()
        for row in data['leagues']['GT']:
            row['balance'] = ''
        schedule = {'sources': {'GT': {'records': [{
            'fixture_status': 'scheduled', 'timestamp_utc': '2099-01-01T10:00:00Z',
            'player': 'Alpha', 'rival': 'Beta',
        }]}}}
        soup = BeautifulSoup(render_page({}, {}, data, schedule), 'html.parser')
        self.assertIn('🟢 Alpha', soup.select_one('#upcoming-matches').text)
        self.assertIn('🔴 Beta', soup.select_one('#upcoming-matches').text)
        self.assertIn('🟢 Alpha', soup.select_one('.streak-panel').text)


if __name__ == '__main__':
    unittest.main()

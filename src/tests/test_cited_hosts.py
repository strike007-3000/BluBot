from scripts.update_config_keywords import cited_hosts


def test_cited_hosts_filters_known_and_platforms():
    html = '<a href="https://www.newlab.ai/post">x</a> <a href="https://github.com/a/b">g</a> <a href="https://blog.known.com/p">k</a>'
    assert cited_hosts(html, {"known.com"}) == {"newlab.ai"}

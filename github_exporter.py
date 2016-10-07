from prometheus_client import start_http_server
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily, REGISTRY

import json, requests, sys, time, os, ast, signal

class GitHubCollector(object):

  def collect(self):
    # Ensure we have something to export
    if os.getenv('REPOS'):
      repos = os.getenv('REPOS').replace(' ','').split(",")
    if os.getenv('ORGS'):
      orgs = os.getenv('ORGS').replace(' ','').split(",")

    metrics = {'forks': 'forks',
               'stars': 'stargazers_count',
               'open_issues': 'open_issues',
               'watchers': 'watchers_count',
               'has_issues': 'has_issues',}

    METRIC_PREFIX = 'github_repo'
    LABELS = ['repo', 'user']
    gauges = {}

    # Setup metric counters from prometheus_client.core
    for metric in metrics:
      gauges[metric] = GaugeMetricFamily('%s_%s' % (METRIC_PREFIX, metric), '%s' % metric, value=None, labels=LABELS)

    # Check the API rate limit
    self._check_api_limit()
    print("Rate Limit Check Completed")

    # loop through specified repositories and organizations and collect metrics
    if os.getenv('REPOS'):
      self._assemble_repo_urls(repos)
      self._collect_repo_metrics(gauges, metrics)
      print("Metrics collected for individually specified repositories")
    if os.getenv('ORGS'):
      self._assemble_org_urls(orgs)
      self._collect_org_metrics(gauges, metrics)
      print("Metrics collected for repositories listed under specified organization")

    # Yield all metrics returned
    for metric in metrics:
      yield gauges[metric]

  def _assemble_repo_urls(self, repos):
    self._repo_url_list = []
    for repo in repos:
      print(repo + " added to collection array")
      self._repo_url_list.extend('https://api.github.com/repos/{0}'.format(repo).split(","))

  def _assemble_org_urls(self, orgs):
    self._org_url_list = []
    for org in orgs:
      print(org + " added to collection array")
      self._org_url_list.extend('https://api.github.com/orgs/{0}/repos'.format(org).split(","))

  def _collect_repo_metrics(self, gauges, metrics):
    for repo in self._repo_url_list:
      print("Collecting metrics for GitHub repository:  " + repo)
      response_json = self._get_json(repo)
      self._add_metrics(gauges, metrics, response_json)

  def _collect_org_metrics(self, gauges, metrics):
    for org in self._org_url_list:
      print(org)
    print(self._org_url_list)
    for org in self._org_url_list:
      print("Collecting metrics for GitHub Org:  " + org)
      response_json = self._get_json(org)
      for repo in response_json:
        self._add_metrics(gauges, metrics, repo)

  def _get_json(self, url):
    print("Getting JSON Payload for " + url)
    response = requests.get(url)
    response_json = json.loads(response.content.decode('UTF-8'))
    return response_json

  def _check_api_limit(self):
    rate_limit_url = "https://api.github.com/rate_limit"

    if os.getenv('GITHUB_TOKEN'):
      print("Authentication token detected: " + os.getenv('GITHUB_TOKEN'))
      payload = {"access_token":os.environ["GITHUB_TOKEN"]}
      R = requests.get(rate_limit_url,params=payload)
    else:
      R = requests.get(rate_limit_url)

    limit_js = ast.literal_eval(R.text)
    remaining = limit_js["rate"]["remaining"]
    print("Requests remaing this hour", remaining)
    if not remaining:
      print("Rate limit exceeded, sleeping for 60 seconds...")
      time.sleep(60)

  def _add_metrics(self, gauges, metrics, response_json):
    for metric, field in metrics.items():
      gauges[metric].add_metric([response_json['name'], response_json['owner']['login']], value=response_json[field])

def sigterm_handler(_signo, _stack_frame):
  sys.exit(0)

if __name__ == '__main__':
  if not (os.getenv('REPOS') or os.getenv('ORGS')):
    print("No repositories or organizations specified, exiting")
    exit(1)
  start_http_server(int(os.getenv('BIND_PORT')))
  REGISTRY.register(GitHubCollector())
  
  signal.signal(signal.SIGTERM, sigterm_handler)
  while True: time.sleep(int(os.getenv('INTERVAL')))

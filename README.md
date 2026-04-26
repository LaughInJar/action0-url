# Action0-Url

Easy URL parsing, manipulation and unparsing wrapper around 
urllib.parse's methods (WIP).

Either with an existing url:

```python
from action0.url import Url

url = Url("https://www.example.com/path/filename.json?foo=bar")
url.query.set("foo", "baz")
print(url.as_str())
# https://www.example.com/path/filename.json?foo=baz
url.query.add("a", "b")
print(url.as_str())
# https://www.example.com/path/filename.json?foo=baz&a=b
url.query.add("foo", "123")
print(url.as_str())
# https://www.example.com/path/filename.json?foo=baz&foo=123&a=b
url.hostname = "action0.com"
url.port = "8443"
url.path = "/public/index.html"
url.username = "user"
url.password = "pass"
url.fragment = "fragment"
# instead of url.as_str() you can also use str(url) or just print(url)
print(url)
```

Or construct one (and manipulate):

```python
from action0.url import Url

url = Url(
    scheme="https",
    hostname="example.com",
    path="index.html",
    query={"a": "b", "foo": ["bar", "baz"]},
    port=1234
)
print(url)
# https://example.com:1234/index.html?a=b&foo=bar&foo=baz
url.username="myuser"
url.port=None
print(url)
# 'https://myuser@example.com/index.html?a=b&foo=bar&foo=baz'
```

## TODOs

 1. Tests
 2. GH-Actions (run linter & test matrix for versions 3.10+)
 3. Docs
 4. Build & publish

## About action0

This is just the namespace I like to use for my personal projects.
I quite like namespaces.
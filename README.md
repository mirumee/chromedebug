chromedebug
===========

A Chrome remote debugging protocol server for Python.

It's quite similar in concept to [Chrome Logger](http://craig.is/writing/chrome-logger/) but allows real-time communication and does not rely on any extensions.


Setting up the server:
----------------------

Start by running your code using the `chromedebug` script.
It will create a new thread and open a websocket for Chrome to connect to.

```
$ chromedebug myfile.py some args
```

Then navigate your browser (a recent release of Chrome is required) to the following url:

```
chrome://devtools/devtools.html?ws=0.0.0.0:9222
```

If Chrome claims that the URL is invalid, enable and disable the DevTools panel (F12) and then it will work.


The console
-----------

The `console` module offers an API similar to the one found in your browser:

```python
from chromedebug import console

console.log('Current time is', datetime.datetime.now())
console.warn('Oh my', None)
console.error('EEEK!')
```

Avoid string interpolation and let the library serialize your objects instead.
You can pass almost any object and then inspect its contents in the browser.


The debugger
------------

This should Just Work™.

```python
from chromedebug import debugger

debugger.set_trace()
```


The profiler
------------

This should Just Work™. Yes, it does say *JavaScript* although it will happily profile your Python code.


Alpha quality
-------------

Please do not use this anywhere near production environments. This is a proof of concept.
Current code hardly ever frees memory and needs lots of refactoring and probably a better API.

**Warning:** Current implementation uses pure Python code which means it's *terribly slow*.

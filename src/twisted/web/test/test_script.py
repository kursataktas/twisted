# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.script}.
"""

import os

from twisted.internet import defer
from twisted.python.filepath import FilePath
from twisted.trial.unittest import SynchronousTestCase, TestCase
from twisted.web.http import NOT_FOUND
from twisted.web.resource import getChildForRequest
from twisted.web.script import (
    PythonScript,
    ResourceScriptDirectory,
    ResourceScriptWrapper,
)
from twisted.web.test._util import _render
from twisted.web.test.requesthelper import DummyRequest


class ResourceScriptWrapperTests(SynchronousTestCase):
    """
    Tests for L{ResourceScriptWrapper}.
    """

    def test_render(self) -> None:
        """
        L{ResourceScriptWrapper} delegates C{render()} to a script
        at a specific path.
        """
        path = self.mktemp()
        with open(path, "w") as f:
            f.write("from twisted.web.pages import errorPage\n")
            f.write('resource = errorPage(418, "I\'m a teapot", "")\n')

        wrapper = ResourceScriptWrapper(path)
        request = DummyRequest([b""])
        self.successResultOf(_render(wrapper, request))
        self.assertEqual(request.responseCode, 418)

    def test_getChildWithDefault(self) -> None:
        """
        L{ResourceScriptWrapper} delegates C{getChildWithDefault()}
        to a script at a specific path.
        """
        path = self.mktemp()
        with open(path, "w") as f:
            f.write("from twisted.web.pages import errorPage, notFound\n")
            f.write("resource = notFound()\n")
            f.write(
                'resource.putChild(b"child", errorPage(418, "I\'m a teapot", ""))\n'
            )

        wrapper = ResourceScriptWrapper(path)
        request = DummyRequest([b"child"])
        resource = getChildForRequest(wrapper, request)
        self.successResultOf(_render(resource, request))
        self.assertEqual(request.responseCode, 418)


class ResourceScriptDirectoryTests(TestCase):
    """
    Tests for L{ResourceScriptDirectory}.
    """

    def test_renderNotFound(self) -> defer.Deferred[None]:
        """
        L{ResourceScriptDirectory.render} sets the HTTP response code to I{NOT
        FOUND}.
        """
        resource = ResourceScriptDirectory(os.fsencode(self.mktemp()))
        request = DummyRequest([b""])
        d = _render(resource, request)

        def cbRendered(ignored: object) -> None:
            self.assertEqual(request.responseCode, NOT_FOUND)

        return d.addCallback(cbRendered)

    def test_notFoundChild(self) -> defer.Deferred[None]:
        """
        L{ResourceScriptDirectory.getChild} returns a resource which renders an
        response with the HTTP I{NOT FOUND} status code if the indicated child
        does not exist as an entry in the directory used to initialized the
        L{ResourceScriptDirectory}.
        """
        path = self.mktemp()
        os.makedirs(path)
        resource = ResourceScriptDirectory(os.fsencode(path))
        request = DummyRequest([b"foo"])
        child = resource.getChild(b"foo", request)
        d = _render(child, request)

        def cbRendered(ignored: object) -> None:
            self.assertEqual(request.responseCode, NOT_FOUND)

        return d.addCallback(cbRendered)

    def test_render(self) -> None:
        """
        L{ResourceScriptDirectory.getChild} returns a resource which renders a
        response with the HTTP 200 status code and the content of the rpy's
        C{request} global.
        """
        tmp = FilePath(self.mktemp())
        tmp.makedirs()
        tmp.child("test.rpy").setContent(
            b"""
from twisted.web.resource import Resource
class TestResource(Resource):
    isLeaf = True
    def render_GET(self, request):
        return b'ok'
resource = TestResource()"""
        )
        resource = ResourceScriptDirectory(tmp._asBytesPath())
        request = DummyRequest([b""])
        child = resource.getChild(b"test.rpy", request)
        self.successResultOf(_render(child, request))
        self.assertEqual(b"".join(request.written), b"ok")


class PythonScriptTests(TestCase):
    """
    Tests for L{PythonScript}.
    """

    def test_notFoundRender(self) -> None:
        """
        If the source file a L{PythonScript} is initialized with doesn't exist,
        L{PythonScript.render} sets the HTTP response code to I{NOT FOUND}.
        """
        resource = PythonScript(self.mktemp(), None)
        request = DummyRequest([b""])
        self.successResultOf(_render(resource, request))
        self.assertEqual(request.responseCode, NOT_FOUND)

    def test_render(self) -> None:
        """
        The source file a L{PythonScript} is initialized with can generate
        a response by calling C{request.write()}.
        """
        tmp = FilePath(self.mktemp())
        tmp.makedirs()
        child = tmp.child("test.epy")
        child.setContent(b'request.write(b"Hello, world!")')
        resource = PythonScript(child._asBytesPath(), None)
        request = DummyRequest([b""])
        self.successResultOf(_render(resource, request))
        self.assertEqual(b"Hello, world!", b"".join(request.written))

    def test_renderException(self) -> None:
        """
        If executing the source file a L{PythonScript} is initialized with
        raises an exception L{PythonScript.render} displays that exception.
        """
        tmp = FilePath(self.mktemp())
        tmp.makedirs()
        child = tmp.child("test.epy")
        child.setContent(b'raise Exception("nooo")')
        resource = PythonScript(child._asBytesPath(), None)
        request = DummyRequest([b""])
        self.successResultOf(_render(resource, request))
        self.assertIn(b"nooo", b"".join(request.written))

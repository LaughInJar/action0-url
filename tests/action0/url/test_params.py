import unittest

from url import Params


class ParamsInitTestCase(unittest.TestCase):
    """
    test for :py:meth:`action0.url.params.Params.__init__`
    """

    def test_separator_init(self):
        """ """
        self.assertEqual(Params().separator, "&")
        self.assertEqual(Params(params=None, separator="&").separator, "&")
        self.assertEqual(Params(None, "&").separator, "&")
        self.assertEqual(Params("a=b", "&").separator, "&")

        self.assertEqual(Params(separator=";").separator, ";")
        self.assertEqual(Params(params=None, separator=";").separator, ";")
        self.assertEqual(Params(None, ";").separator, ";")
        self.assertEqual(Params("a=b", ";").separator, ";")

    def test_emtpy_init(self):
        """
        Test initialization with no params
        """
        params = Params()
        self.assertEqual(params.as_str(), "")
        self.assertEqual(params.separator, "&")

    def test_emtpy_init_with_none(self):
        """
        Test initialization with `None` for params
        """
        params = Params(None)
        self.assertEqual(params.as_str(), "")
        self.assertEqual(params.separator, "&")

        params = Params(params=None)
        self.assertEqual(params.as_str(), "")
        self.assertEqual(params.separator, "&")

    def test_emtpy_init_with_separator(self):
        """
        Test initialization with `None` for params and a separator
        """
        params = Params(separator=";")
        self.assertEqual(params.as_str(), "")
        self.assertEqual(params.separator, ";")

        params = Params(None, ";")
        self.assertEqual(params.as_str(), "")
        self.assertEqual(params.separator, ";")

        params = Params(params=None, separator=";")
        self.assertEqual(params.as_str(), "")
        self.assertEqual(params.separator, ";")


if __name__ == "__main__":
    unittest.main()

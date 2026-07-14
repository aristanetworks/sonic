def test_parser_registration_is_nonduplicative():
   # pylint: disable=import-outside-toplevel
   from arista.cli.args import _duplicates, registeredParsers
   assert registeredParsers and not _duplicates

"""
V4 Integration Tests

This package contains integration tests that verify component interactions
in the V4 email processing pipeline.

Test Categories:
- ConfigLoader ↔ AccountProcessor integration
- Rules Engine ↔ processing pipeline integration
- Content Parser ↔ LLM processing integration
- End-to-end scenarios

All tests use mock external services (IMAP, LLM) to enable testing without
real dependencies.
"""

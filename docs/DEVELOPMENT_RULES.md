# Development Rules

- Preserve the existing architecture and do not unnecessarily rewrite working code.
- Do not introduce unnecessary dependencies.
- Do not use LangChain for the entire system.
- Keep backend code modular.
- Use environment variables for configuration.
- Never expose credentials or commit `.env`.
- Use meaningful variable and function names.
- Handle exceptions properly and report actionable errors.
- Validate uploaded files, including content where practical.
- Use appropriate HTTP status codes.
- Keep database operations transactional and maintain consistency with stored files.
- Use reusable functions and FastAPI dependencies.
- Avoid duplicate implementations, especially HTTP client and configuration setup.
- Write and run tests for implemented functionality; report only tests actually executed.
- Explain significant changes.
- Do not implement features outside the current module.
- Understand the purpose and callers of existing files before modifying them.
- Update relevant documentation whenever implementation changes.

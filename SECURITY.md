# Security Policy

audx is local-first software. It should not make network requests during normal
music-making workflows.

## Reporting a Vulnerability

Please report security issues privately to:

`chrisschofield@totalaudiopromo.com`

Include:

- affected version or commit
- operating system
- reproduction steps
- whether local files, network access, or credentials are involved

## Local File Access

The browser UI served by `audx serve` can read local audio/project files through
localhost endpoints. Only run it on trusted machines and keep the default
localhost binding unless you intentionally want another device on your network
to connect.

## AI and Network Features

AI-related features are opt-in and require user-provided credentials. API keys
must not be stored in `.audx` project files.

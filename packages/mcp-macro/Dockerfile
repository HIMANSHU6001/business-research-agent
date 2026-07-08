FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml .
COPY src/ ./src/

# Install the package
RUN uv pip install --system -e .

# Expose port
EXPOSE 8000

# Run the MCP server with SSE transport
CMD ["python", "-m", "data360.mcp_server", "--transport", "sse", "--port", "8000"]

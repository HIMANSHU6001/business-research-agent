FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir mcp fastmcp duckdb "pandas<3.0.0" numpy scipy statsmodels uvicorn pyarrow

COPY . .

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]

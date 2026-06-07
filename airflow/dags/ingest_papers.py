async def ingest_papers():
    pass

#todo:
# get papers from the arxiv client with retry logic and error handling
# transform papers into the format expecetd by the database client
# process papers in batches to avoid memory issues and optimize database writes
# implement logging at each step to track progress and catch issues
# ensure idempotency: if the same paper is ingested multiple times,
# it should not create duplicates in the database
# handle edge cases, such as missing fields in the arXiv data, or papers that fail to parse
# consider adding metrics (e.g. number of papers ingested, time taken) for monitoring and alerting
# overall, this function should reliably fetch the latest papers from arXiv,
# transform them as needed, and then efficiently and safely
# store papers in the database.

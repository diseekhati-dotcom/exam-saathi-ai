from .official_search import search_exam

async def find_pyq(exam):
    return await search_exam(exam,'pyq')

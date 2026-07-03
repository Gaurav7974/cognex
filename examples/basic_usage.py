import sys
import asyncio
sys.path.insert(0, '../src')
from cognex_mcp.tools import handle_tool_call

async def main():
    result = await handle_tool_call('memory_add', {'content': 'Always use type hints in Python code', 'memory_type': 'preference', 'project': 'example'})
    print('Added:', result)
    result = await handle_tool_call('memory_search', {'query': 'python', 'project': 'example'})
    print('Found:', result)
if __name__ == '__main__':
    asyncio.run(main())
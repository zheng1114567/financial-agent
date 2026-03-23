from langchain_community.agent_toolkits.file_management import FileManagementToolkit

from agent.src.agent.shared import AGENT_ROOT

file_tools = FileManagementToolkit(root_dir=AGENT_ROOT).get_tools()
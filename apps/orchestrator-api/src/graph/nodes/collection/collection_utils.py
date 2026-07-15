from typing import TypedDict, Annotated
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

class ReactAgentState(TypedDict):
    messages: Annotated[list, add_messages]


def compress_agent_messages(messages, max_chars=6000):
    """Compress message history to stay within token limits.

    Preserves:
    - System prompt (first SystemMessage)
    - Research brief (first HumanMessage)
    - Last few messages (recent context with valid tool-call pairs)

    Compresses everything in between into a compact summary.
    Reusable across all agents.
    """
    total_chars = 0
    for m in messages:
        total_chars += len(str(getattr(m, 'content', '') or ''))
        if hasattr(m, 'tool_calls') and m.tool_calls:
            for tc in m.tool_calls:
                total_chars += len(str(tc.get('args', {})))

    if total_chars <= max_chars or len(messages) <= 6:
        return messages

    head = messages[:2]

    tail_idx = max(2, len(messages) - 4)
    while tail_idx > 2 and hasattr(messages[tail_idx], 'type') and messages[tail_idx].type == 'tool':
        tail_idx -= 1
    tail = messages[tail_idx:]

    middle = messages[2:tail_idx]
    if not middle:
        return messages

    compressed_middle = []
    i = 0
    while i < len(middle):
        msg = middle[i]
        
        if isinstance(msg, AIMessage) and getattr(msg, 'tool_calls', None):
            # Check if this AIMessage only contains 'think' tool calls
            is_think = all(tc.get('name') == 'think' for tc in msg.tool_calls)
            if is_think:
                i += 1
                # Skip the corresponding ToolMessage(s) for 'think'
                while i < len(middle) and isinstance(middle[i], ToolMessage):
                    i += 1
                continue
            
            # Keep other AIMessages intact
            compressed_middle.append(msg)
            
        elif isinstance(msg, ToolMessage):
            # Truncate content of other tool messages
            content = str(msg.content or '')
            if len(content) > 500:
                compressed_middle.append(ToolMessage(
                    content=content[:500] + "\n...[TRUNCATED FOR TOKEN LIMITS]...",
                    name=msg.name,
                    tool_call_id=msg.tool_call_id
                ))
            else:
                compressed_middle.append(msg)
        else:
            compressed_middle.append(msg)
            
        i += 1

    return head + compressed_middle + tail


def create_thinking_react_agent(model, tools):
    """Creates a React agent that is forced by flow to use the 'think' tool first and after every other tool.
    Automatically compresses message history before each LLM call to stay within token limits."""
    tool_node = ToolNode(tools)
    bound_model = model.bind_tools(tools, parallel_tool_calls=False)
    
    async def agent_node(state: ReactAgentState):
        messages = compress_agent_messages(state["messages"])
        
        force_think = False
        if messages:
            last_msg = messages[-1]
            if isinstance(last_msg, HumanMessage):
                force_think = True
            elif hasattr(last_msg, "type") and last_msg.type == "tool" and getattr(last_msg, "name", "") != "think":
                force_think = True
                
        if force_think:
            prompt_injection = HumanMessage(content="You MUST invoke the `think` tool to reflect on your next steps. DO NOT output conversational text. ONLY output the tool call.")
            response = await bound_model.ainvoke(messages + [prompt_injection], tool_choice="required")
        else:
            response = await bound_model.ainvoke(messages)
            
        return {"messages": [response]}
        
    def should_continue(state: ReactAgentState):
        messages = state["messages"]
        last_message = messages[-1]
        
        if not getattr(last_message, "tool_calls", None):
            return END
        return "tools"
        
    builder = StateGraph(ReactAgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", should_continue, ["tools", END])
    builder.add_edge("tools", "agent")
    
    return builder.compile()

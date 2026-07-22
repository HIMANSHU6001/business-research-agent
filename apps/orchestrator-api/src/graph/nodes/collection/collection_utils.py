from typing import TypedDict, Annotated
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.prebuilt import ToolNode
import asyncio
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


def create_react_agent(model, tools, parallel_tool_calls=True):
    """Creates a React agent.
    Automatically compresses message history before each LLM call to stay within token limits."""
    tool_node = ToolNode(tools)
    bound_model = model.bind_tools(tools, parallel_tool_calls=parallel_tool_calls)
    
    async def agent_node(state: ReactAgentState):
        messages = compress_agent_messages(state["messages"])
        
        # Sanitize tool names in the history to prevent Groq API validation errors
        sanitized_messages = []
        for msg in messages:
            if isinstance(msg, AIMessage):
                new_tcs = []
                for tc in getattr(msg, 'tool_calls', []) or []:
                    name = tc.get("name", "")
                    if " " in name or "{" in name:
                        tc = dict(tc)
                        tc["name"] = name.split()[0].split("{")[0].strip()
                    new_tcs.append(tc)
                    
                new_invalid_tcs = []
                for tc in getattr(msg, 'invalid_tool_calls', []) or []:
                    name = tc.get("name", "")
                    if " " in name or "{" in name:
                        tc = dict(tc)
                        tc["name"] = name.split()[0].split("{")[0].strip()
                    new_invalid_tcs.append(tc)
                    
                new_additional = {}
                for k, v in getattr(msg, "additional_kwargs", {}).items():
                    if k == "tool_calls" and isinstance(v, list):
                        new_add_tcs = []
                        for add_tc in v:
                            if isinstance(add_tc, dict) and "function" in add_tc and isinstance(add_tc["function"], dict):
                                name = add_tc["function"].get("name", "")
                                if isinstance(name, str) and (" " in name or "{" in name):
                                    add_tc = dict(add_tc)
                                    add_tc["function"] = dict(add_tc["function"])
                                    add_tc["function"]["name"] = name.split()[0].split("{")[0].strip()
                            new_add_tcs.append(add_tc)
                        new_additional[k] = new_add_tcs
                    else:
                        new_additional[k] = v
                        
                msg_copy = AIMessage(
                    content=msg.content, 
                    tool_calls=new_tcs, 
                    invalid_tool_calls=new_invalid_tcs,
                    id=getattr(msg, "id", None), 
                    name=getattr(msg, "name", None),
                    additional_kwargs=new_additional,
                    response_metadata=getattr(msg, "response_metadata", {})
                )
                sanitized_messages.append(msg_copy)
            elif isinstance(msg, ToolMessage) and getattr(msg, "name", None):
                name = msg.name
                if " " in name or "{" in name:
                    msg_copy = ToolMessage(
                        content=msg.content, 
                        tool_call_id=msg.tool_call_id, 
                        name=name.split()[0].split("{")[0].strip(), 
                        id=getattr(msg, "id", None),
                        additional_kwargs=getattr(msg, "additional_kwargs", {})
                    )
                    sanitized_messages.append(msg_copy)
                else:
                    sanitized_messages.append(msg)
            else:
                sanitized_messages.append(msg)
                
        # Retry loop to handle Groq API aborting the stream when the LLM hallucinates tool names
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await asyncio.sleep(1) # Throttle to prevent Groq API rate limits
                if attempt < max_retries - 1:
                    response = await bound_model.ainvoke(sanitized_messages)
                else:
                    # Final retry: invoke without tool bindings so Groq can't reject hallucinated tool names.
                    # This produces a plain text response, which causes should_continue -> END gracefully.
                    print("Final retry: invoking model without tools to avoid Groq tool validation crash.")
                    response = await model.ainvoke(sanitized_messages)
                return {"messages": [response]}
            except Exception as e:
                err_str = str(e).lower()
                if ("tool call validation failed" in err_str or "failed to call a function" in err_str) and attempt < max_retries - 1:
                    print(f"Caught Groq API tool hallucination error, retrying ({attempt+1}/{max_retries})...")
                    # Append a strict warning to the history for the retry
                    warning = SystemMessage(content="SYSTEM ERROR: Your previous tool call was rejected because you put JSON arguments inside the tool name. When calling a tool, put ONLY the tool name (e.g. 'search_context') in the name field. Put your arguments in the arguments field separately.")
                    sanitized_messages.append(warning)
                else:
                    raise e
        
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

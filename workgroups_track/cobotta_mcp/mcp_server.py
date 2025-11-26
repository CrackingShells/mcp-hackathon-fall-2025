#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DENSO Robot b-CAP MCP Server

This MCP Server encapsulates the DENSO robot's b-CAP protocol client,
allowing safe interaction with the robot through Model Context Protocol.

Features include:
- Connection management and status queries
- Robot variable reading
- Robot motion control (joint space and Cartesian space)
- Complete operation logging

Safety Notes:
- All motion operations will actually move the robot
- Ensure robot workspace safety before use
- Recommend testing at low speeds
- All operations are logged
"""

import json
import logging
import time
from typing import Optional, Any, Dict
from datetime import datetime

from mcp.server import Server
from mcp.types import Tool, TextContent, Resource, ResourceTemplate
import mcp.server.stdio

from bcapclient import BCAPClient
from orinexception import ORiNException, HResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("denso-bcap-mcp")

# Create MCP Server
app = Server("denso-bcap-server")

# Global state management
class ServerState:
    def __init__(self):
        self.client: Optional[BCAPClient] = None
        self.controller_handle: Optional[int] = None
        self.robot_handle: Optional[int] = None
        self.connection_info: Dict[str, Any] = {}
        self.operation_log: list = []
    
    def log_operation(self, operation: str, params: dict, result: Any = None, error: str = None):
        """Log operation"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "params": params,
            "result": str(result) if result is not None else None,
            "error": error
        }
        self.operation_log.append(log_entry)
        logger.info(f"Operation: {operation}, Params: {params}, Result: {result}, Error: {error}")
    
    def reset(self):
        """Reset all connections"""
        if self.client:
            if self.robot_handle:
                self.client.robot_release(self.robot_handle)
            if self.controller_handle:
                self.client.controller_disconnect(self.controller_handle)
        self.client = None
        self.controller_handle = None
        self.robot_handle = None
        self.connection_info = {}

state = ServerState()

# ============================================================================
# MCP Tools Definition
# ============================================================================

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools"""
    return [
        # Connection Management
        Tool(
            name="bcap_connect",
            description="""Establish network connection to DENSO robot controller.
            
Use Case: This is the first step for all operations. Must establish connection before executing other operations.
Parameters: Requires robot controller IP address, port defaults to 5007.
Note: If connection already exists, will disconnect old connection before establishing new one.
Returns: Connection information and timestamp upon successful connection.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "Robot controller IP address"
                    },
                    "port": {
                        "type": "integer",
                        "description": "b-CAP service port",
                        "default": 5007
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Connection timeout in seconds",
                        "default": 3.0
                    }
                },
                "required": ["host"]
            }
        ),
        Tool(
            name="bcap_disconnect",
            description="""Disconnect from robot controller and release all resources.
            
Use Case: Should call this tool to disconnect after completing all operations.
Functionality: Automatically releases robot handle, controller handle, and network connection.
Note: After disconnection, must call bcap_connect again to continue operations.""",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="bcap_get_connection_status",
            description="""Query current connection status with robot.
            
Use Case: Check if connected, which controller is connected, and if robot is connected.
Returns: Network connection status, controller connection status, robot connection status, and detailed connection information.
Typical Usage: Check connection status before executing operations, or troubleshoot connection issues.""",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        
        # Controller Operations
        Tool(
            name="bcap_controller_connect",
            description="""Connect to robot controller and obtain controller handle.
            
Prerequisite: Must call bcap_connect first to establish network connection.
Use Case: Second step after establishing network connection, to obtain controller access.
Parameters: provider defaults to "CaoProv.DENSO.VRC" (simulator), use "CaoProv.DENSO.RC8" for real robot.
Returns: Controller handle for subsequent operations.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Controller name",
                        "default": ""
                    },
                    "provider": {
                        "type": "string",
                        "description": "Provider name",
                        "default": "CaoProv.DENSO.VRC"
                    },
                    "machine": {
                        "type": "string",
                        "description": "Machine name",
                        "default": "localhost"
                    },
                    "option": {
                        "type": "string",
                        "description": "Optional parameters",
                        "default": ""
                    }
                }
            }
        ),
        Tool(
            name="bcap_controller_get_robot_names",
            description="""Get list of all available robot names on controller.
            
Prerequisite: Must call bcap_controller_connect first.
Use Case: View all robots managed by controller to determine which robot to connect to.
Returns: List of robot names, typically includes "Arm", "Robot1", etc.
Typical Usage: View available robot list before connecting to robot.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "option": {
                        "type": "string",
                        "description": "Optional parameters",
                        "default": ""
                    }
                }
            }
        ),
        Tool(
            name="bcap_controller_get_variable_names",
            description="""Get list of all available variable names on controller.
            
Prerequisite: Must call bcap_controller_connect first.
Use Case: View all available controller-level variables for system status queries.
Returns: List of variable names, may include system status, configuration parameters, etc.
Note: These are controller-level variables, different from robot variables.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "option": {
                        "type": "string",
                        "description": "Optional parameters",
                        "default": ""
                    }
                }
            }
        ),
        Tool(
            name="bcap_controller_clear_error",
            description="""Clear controller error and alarm status.
            
Prerequisite: Must call bcap_controller_connect first.
Use Case: Use this tool to clear error status when robot encounters errors or alarms.
Functionality: Executes "ClearError" command to clear controller error flags.
Note: If error cannot be cleared (e.g., hardware failure), may need to check hardware or restart controller.
Typical Usage: After robot error occurs, fix the problem, then call this tool to clear error and continue operations.""",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        
        # Robot Operations
        Tool(
            name="bcap_robot_connect",
            description="""Connect to specified robot and obtain robot handle.
            
Prerequisite: Must call bcap_controller_connect first.
Use Case: Third step after connecting to controller, to obtain access to specific robot.
Parameters: name defaults to "Arm", specify robot name if controller manages multiple robots.
Returns: Robot handle for subsequent robot operations (queries, movements, etc.).
Typical Flow: bcap_connect → bcap_controller_connect → bcap_robot_connect → execute robot operations.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Robot name",
                        "default": "Arm"
                    },
                    "option": {
                        "type": "string",
                        "description": "Optional parameters",
                        "default": ""
                    }
                }
            }
        ),
        Tool(
            name="bcap_robot_get_variable",
            description="""Get current value of specified robot variable.
            
Prerequisite: Must call bcap_robot_connect first.
Use Case: Query robot status information such as current position, joint angles, speed, etc.
Common Variables:
  - @CURRENT_POSITION: Current Cartesian position [x, y, z, rx, ry, rz]
  - @CURRENT_ANGLE: Current joint angles [j1, j2, j3, j4, j5, j6]
  - @SPEED: Current speed setting
Returns: Actual value of variable, type depends on variable (array, numeric, etc.).""",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Variable name, e.g. @CURRENT_POSITION"
                    },
                    "option": {
                        "type": "string",
                        "description": "Optional parameters",
                        "default": ""
                    }
                },
                "required": ["name"]
            }
        ),
        Tool(
            name="bcap_robot_get_variable_names",
            description="""Get list of all available variable names on robot.
            
Prerequisite: Must call bcap_robot_connect first.
Use Case: View which variables robot supports, for exploring queryable status information.
Returns: List of all available variable names.
Typical Usage: When unsure of variable names, first call this tool to view all available variables, then use bcap_robot_get_variable to get specific values.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "option": {
                        "type": "string",
                        "description": "Optional parameters",
                        "default": ""
                    }
                }
            }
        ),
        
        # Robot Motion Control
        Tool(
            name="bcap_robot_move_to_joint_angles",
            description="""Move robot to specified joint angles (joint space/PTP motion).
            
⚠️ WARNING: This operation will actually move the robot, ensure workspace safety!
Prerequisite: Must call bcap_robot_connect first.
Use Case: Need precise control of each joint angle, or avoid Cartesian space singularities.
Parameters: joint_angles must be array of 6 numeric values in degrees.
Motion Type: Joint space interpolation (PTP), each joint moves independently to target angle.
Returns: Target angles, previous angles, and safety warning.
Note: Motion command is asynchronous, returns immediately after sending, robot executes motion in background.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "joint_angles": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Target joint angles list in degrees, e.g. [0, 0, 0, 0, 0, 0]",
                        "minItems": 6,
                        "maxItems": 6
                    },
                    "option": {
                        "type": "string",
                        "description": "Optional parameters such as speed settings",
                        "default": ""
                    }
                },
                "required": ["joint_angles"]
            }
        ),
        Tool(
            name="bcap_robot_move_to_pose",
            description="""Move robot to specified position and orientation (Cartesian space motion).
            
⚠️ WARNING: This operation will actually move the robot, ensure workspace safety!
Prerequisite: Must call bcap_robot_connect first.
Use Case: Need precise control of end-effector spatial position and orientation.
Parameters: pose is array of 6 numeric values [x, y, z, rx, ry, rz]
  - x, y, z: Position coordinates in millimeters (mm)
  - rx, ry, rz: Orientation angles in degrees
Motion Type: Cartesian space interpolation, end-effector moves along straight line or planned path.
Returns: Target pose, previous pose, and safety warning.
Note: May encounter singularities or exceed workspace boundaries.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "pose": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Target position and orientation [x(mm), y(mm), z(mm), rx(deg), ry(deg), rz(deg)]",
                        "minItems": 6,
                        "maxItems": 6
                    },
                    "option": {
                        "type": "string",
                        "description": "Optional parameters such as speed settings",
                        "default": ""
                    }
                },
                "required": ["pose"]
            }
        ),
        Tool(
            name="bcap_robot_gohome",
            description="""Move robot back to predefined home position.
            
Prerequisite: Must call bcap_robot_connect first.
Use Case: Move robot to safe initial position, or reset after completing tasks.
Functionality: Executes robot_gohome command, robot automatically moves to home configuration position.
Safety: Relatively safe operation, home position is typically pre-configured safe position.
Returns: Previous joint angles and safety warning.
Note: Home position determined by robot controller configuration, may differ between robots.""",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="bcap_robot_set_speed",
            description="""Set robot motion speed.
            
Prerequisite: Must call bcap_robot_connect first.
Use Case: Adjust speed before executing motion, e.g., use low speed for testing, high speed for production.
Parameters:
  - axis: 0 for all axes, 1-6 for specific axis
  - speed: Speed value, typically percentage (0-100)
Functionality: Setting affects all subsequent motion commands.
Returns: Set axis and speed value.
Typical Usage: Set appropriate speed before executing motion, recommend 20-30% speed for testing.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "axis": {
                        "type": "integer",
                        "description": "Axis number (1-6), 0 for all axes",
                        "default": 0
                    },
                    "speed": {
                        "type": "number",
                        "description": "Speed value (percentage, typically 0-100)",
                        "default": 50.0
                    }
                }
            }
        ),
        Tool(
            name="bcap_robot_execute_trajectory",
            description="""Execute multiple joint angle motions in batch, robot moves to each target position sequentially.
            
⚠️ WARNING: This operation will move robot multiple times continuously, ensure entire trajectory path is safe!
Prerequisite: Must call bcap_robot_connect first.
Use Case: Need to execute series of continuous motions, such as drawing trajectories, executing complex tasks, etc.
Parameters: trajectory is 2D array, each element is 6 joint angles in degrees
  Example: [[0,0,0,0,0,0], [10,20,30,0,0,0], [20,40,60,0,0,0]]
Functionality: Executes each trajectory point sequentially, continues to subsequent points even if one point fails.
Returns: Detailed execution report including successful points, failed points, and initial position.
Advantage: Complete multiple motions in one call, more convenient than multiple single-step motion calls.
Note: Motions between trajectory points are independent, smooth transition not guaranteed.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "trajectory": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 6,
                            "maxItems": 6
                        },
                        "description": "Trajectory point list, each point is 6 joint angles in degrees, e.g. [[0,0,0,0,0,0], [10,20,30,0,0,0]]",
                        "minItems": 1
                    },
                    "option": {
                        "type": "string",
                        "description": "Optional parameters such as speed settings",
                        "default": ""
                    }
                },
                "required": ["trajectory"]
            }
        ),
        Tool(
            name="bcap_robot_execute_slave_trajectory",
            description="""Execute continuous trajectory motion using slave mode for smooth and fluent movement.
            
⚠️ WARNING: This operation will move robot continuously along the trajectory, ensure entire path is safe!
Prerequisite: Must call bcap_robot_connect first.
Use Case: Need smooth continuous trajectory motion, such as circular paths, complex curves, etc.
Parameters: trajectory is 2D array, each element is 6 joint angles in degrees
  Example: [[0,0,0,0,0,0], [10,20,30,0,0,0], [20,40,60,0,0,0]]
Functionality: Uses DENSO slave mode (slvChangeMode + slvMove) for continuous smooth motion.
  - Enters slave mode (0x202)
  - Sends each trajectory point via slvMove for continuous motion
  - Exits slave mode (0x000) after completion
Returns: Detailed execution report including successful points, failed points, and initial position.
Advantage: Provides smooth continuous motion, better than sequential robot_move calls.
Note: Slave mode provides smoother transitions between trajectory points compared to standard trajectory execution.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "trajectory": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "number"},
                            "minItems": 6,
                            "maxItems": 6
                        },
                        "description": "Trajectory point list, each point is 6 joint angles in degrees, e.g. [[0,0,0,0,0,0], [10,20,30,0,0,0]]",
                        "minItems": 1
                    },
                    "option": {
                        "type": "string",
                        "description": "Optional parameters",
                        "default": ""
                    }
                },
                "required": ["trajectory"]
            }
        ),
        
        # Gripper Control
        Tool(
            name="bcap_robot_open_gripper",
            description="""Open robot gripper to specified distance.
            
Prerequisite: Must call bcap_controller_connect first.
Use Case: Open gripper to release object or prepare for picking.
Functionality: Executes HandMoveA command via controller_execute to open the gripper.
Parameters:
  - dist: Distance in meters (0 to 0.03), default 0.030 (30mm, maximum open)
  - speed: Speed value (0-100), default 100
Returns: Success status and message.
Note: Uses HandMoveA command, same as cobotta_x_RIKEN.py implementation.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "dist": {
                        "type": "number",
                        "description": "Distance in meters (0 to 0.03), default 0.030 (30mm, maximum open)",
                        "default": 0.030
                    },
                    "speed": {
                        "type": "number",
                        "description": "Speed value (0-100), default 100",
                        "default": 30
                    }
                }
            }
        ),
        Tool(
            name="bcap_robot_close_gripper",
            description="""Close robot gripper to specified distance.
            
Prerequisite: Must call bcap_robot_connect first.
Use Case: Close gripper to grasp and hold object.
Functionality: Executes HandMoveA command via controller_execute to close the gripper.
Parameters:
  - dist: Distance in meters (0 to 0.03), default 0.0 (fully closed)
  - speed: Speed value (0-100), default 100
Returns: Success status and message.
Note: Uses HandMoveA command, same as cobotta_x_RIKEN.py implementation.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "dist": {
                        "type": "number",
                        "description": "Distance in meters (0 to 0.03), default 0.0 (fully closed)",
                        "default": 0.0
                    },
                    "speed": {
                        "type": "number",
                        "description": "Speed value (0-100), default 100",
                        "default": 100
                    }
                }
            }
        ),
        
        # High-level Operations
        Tool(
            name="bcap_robot_pick_and_place",
            description="""Execute a complete pick-and-place operation sequence.
            
⚠️ WARNING: This operation will move the robot through multiple steps. Ensure workspace safety!
Prerequisite: Must call bcap_controller_connect and bcap_robot_connect first.
Use Case: Automated pick-and-place tasks with gripper control.
Operation Sequence:
  0. Record initial position
  1. Open gripper (prepare for picking)
  2. Move down along Z-axis (pick_down_distance)
  3. Close gripper to grasp object (close to 21mm)
  4-6. Move up along Z-axis (lift_up_distance, 3 steps)
  7. Move along Y-axis (place_y_offset)
  8. Move down along Z-axis (place_down_distance)
  9. Open gripper to release object
  10. Return to initial position
Parameters:
  - pick_down_distance: Distance to move down for picking (cm), default 4.0
  - lift_up_distance: Total distance to lift up (cm), default 9.0 (3cm × 3 steps)
  - place_y_offset: Y-axis offset for placing (cm), default 2.5
  - place_down_distance: Distance to move down for placing (cm), default 3.0
  - gripper_speed: Gripper operation speed (0-100), default 100
Returns: Detailed execution report with all step results.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "pick_down_distance": {
                        "type": "number",
                        "description": "Distance to move down for picking (cm), default 4.0",
                        "default": 4.0
                    },
                    "lift_up_distance": {
                        "type": "number",
                        "description": "Total distance to lift up (cm), default 9.0",
                        "default": 9.0
                    },
                    "place_y_offset": {
                        "type": "number",
                        "description": "Y-axis offset for placing (cm), default 2.5",
                        "default": 2.5
                    },
                    "place_down_distance": {
                        "type": "number",
                        "description": "Distance to move down for placing (cm), default 3.0",
                        "default": 3.0
                    },
                    "gripper_speed": {
                        "type": "number",
                        "description": "Gripper operation speed (0-100), default 100",
                        "default": 100
                    }
                }
            }
        ),
        
        # Logging and Debugging
        Tool(
            name="bcap_get_operation_log",
            description="""Get historical log records of all operations.
            
Use Case: View all previously executed operations for debugging, auditing, or understanding operation history.
Parameters: limit specifies returning most recent N log entries, defaults to 50.
Returns: Contains timestamp, operation name, parameters, result, and error information (if any) for each operation.
Typical Usage:
  - View operation sequence when debugging
  - View failed operations when troubleshooting errors
  - Understand what operations were previously executed
Log Content: Records all operations executed through MCP, including successful and failed operations.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Return most recent N log entries",
                        "default": 50
                    }
                }
            }
        ),
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""
    try:
        if name == "bcap_connect":
            return await handle_connect(arguments)
        elif name == "bcap_disconnect":
            return await handle_disconnect(arguments)
        elif name == "bcap_get_connection_status":
            return await handle_get_connection_status(arguments)
        elif name == "bcap_controller_connect":
            return await handle_controller_connect(arguments)
        elif name == "bcap_controller_get_robot_names":
            return await handle_controller_get_robot_names(arguments)
        elif name == "bcap_controller_get_variable_names":
            return await handle_controller_get_variable_names(arguments)
        elif name == "bcap_controller_clear_error":
            return await handle_controller_clear_error(arguments)
        elif name == "bcap_robot_connect":
            return await handle_robot_connect(arguments)
        elif name == "bcap_robot_get_variable":
            return await handle_robot_get_variable(arguments)
        elif name == "bcap_robot_get_variable_names":
            return await handle_robot_get_variable_names(arguments)
        elif name == "bcap_robot_move_to_joint_angles":
            return await handle_robot_move_to_joint_angles(arguments)
        elif name == "bcap_robot_move_to_pose":
            return await handle_robot_move_to_pose(arguments)
        elif name == "bcap_robot_gohome":
            return await handle_robot_gohome(arguments)
        elif name == "bcap_robot_set_speed":
            return await handle_robot_set_speed(arguments)
        elif name == "bcap_robot_execute_trajectory":
            return await handle_robot_execute_trajectory(arguments)
        elif name == "bcap_robot_execute_slave_trajectory":
            return await handle_robot_execute_slave_trajectory(arguments)
        elif name == "bcap_robot_open_gripper":
            return await handle_robot_open_gripper(arguments)
        elif name == "bcap_robot_close_gripper":
            return await handle_robot_close_gripper(arguments)
        elif name == "bcap_robot_pick_and_place":
            return await handle_robot_pick_and_place(arguments)
        elif name == "bcap_get_operation_log":
            return await handle_get_operation_log(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    except ORiNException as e:
        error_msg = f"ORiN error (HResult={e.hresult}): {get_error_description(e.hresult)}"
        state.log_operation(name, arguments, error=error_msg)
        return [TextContent(type="text", text=json.dumps({
            "success": False,
            "error": error_msg,
            "hresult": e.hresult
        }, ensure_ascii=False, indent=2))]
    
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        state.log_operation(name, arguments, error=error_msg)
        return [TextContent(type="text", text=json.dumps({
            "success": False,
            "error": error_msg
        }, ensure_ascii=False, indent=2))]

# ============================================================================
# Tool handler functions
# ============================================================================

async def handle_connect(args: dict) -> list[TextContent]:
    """Handle connection request"""
    host = args["host"]
    port = args.get("port", 5007)
    timeout = args.get("timeout", 3.0)
    
    if state.client:
        state.reset()
    
    state.client = BCAPClient(host, port, timeout)
    state.connection_info = {
        "host": host,
        "port": port,
        "timeout": timeout,
        "connected_at": datetime.now().isoformat()
    }
    
    result = {
        "success": True,
        "message": f"Successfully connected to {host}:{port}",
        "connection_info": state.connection_info
    }
    
    state.log_operation("bcap_connect", args, result)
    
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

async def handle_disconnect(args: dict) -> list[TextContent]:
    """Handle disconnect request"""
    if not state.client:
        return [TextContent(type="text", text=json.dumps({
            "success": False,
            "error": "Not connected"
        }, ensure_ascii=False, indent=2))]
    
    state.reset()
    result = {"success": True, "message": "Disconnected"}
    state.log_operation("bcap_disconnect", args, result)
    
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

async def handle_get_connection_status(args: dict) -> list[TextContent]:
    """Get connection status"""
    result = {
        "connected": state.client is not None,
        "controller_connected": state.controller_handle is not None,
        "robot_connected": state.robot_handle is not None,
        "connection_info": state.connection_info if state.client else None
    }
    
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

async def handle_controller_connect(args: dict) -> list[TextContent]:
    """Connect to controller"""
    if not state.client:
        raise Exception("Please call bcap_connect first to establish connection")
    
    name = args.get("name", "")
    provider = args.get("provider", "CaoProv.DENSO.VRC")
    machine = args.get("machine", "localhost")
    option = args.get("option", "")
    
    state.controller_handle = state.client.controller_connect(name, provider, machine, option)
    
    result = {
        "success": True,
        "controller_handle": state.controller_handle,
        "message": "Successfully connected to controller"
    }
    
    state.log_operation("bcap_controller_connect", args, result)
    
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

async def handle_controller_get_robot_names(args: dict) -> list[TextContent]:
    """Get robot name list"""
    if not state.controller_handle:
        raise Exception("Please call bcap_controller_connect first")
    
    option = args.get("option", "")
    robot_names = state.client.controller_getrobotnames(state.controller_handle, option)
    
    result = {
        "success": True,
        "robot_names": robot_names
    }
    
    state.log_operation("bcap_controller_get_robot_names", args, result)
    
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

async def handle_controller_get_variable_names(args: dict) -> list[TextContent]:
    """Get controller variable name list"""
    if not state.controller_handle:
        raise Exception("Please call bcap_controller_connect first")
    
    option = args.get("option", "")
    variable_names = state.client.controller_getvariablenames(state.controller_handle, option)
    
    result = {
        "success": True,
        "variable_names": variable_names
    }
    
    state.log_operation("bcap_controller_get_variable_names", args, result)
    
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

async def handle_controller_clear_error(args: dict) -> list[TextContent]:
    """Clear controller errors and alarms"""
    if not state.controller_handle:
        raise Exception("Please call bcap_controller_connect first")
    
    # Execute clear error command
    # controller_execute(handle, "ClearError", None)
    result_value = state.client.controller_execute(state.controller_handle, "ClearError", None)
    
    result = {
        "success": True,
        "message": "Clear error command executed",
        "result": result_value,
        "note": "If error still exists, may need to check hardware or restart controller"
    }
    
    state.log_operation("bcap_controller_clear_error", args, result)
    
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

async def handle_robot_connect(args: dict) -> list[TextContent]:
    """Connect to robot"""
    if not state.controller_handle:
        raise Exception("Please call bcap_controller_connect first")
    
    name = args.get("name", "Arm")
    option = args.get("option", "")
    
    state.robot_handle = state.client.controller_getrobot(state.controller_handle, name, option)
    
    # Note: Do not execute TakeArm on connection, but before each motion operation, consistent with read_joint_angles.py
    
    result = {
        "success": True,
        "robot_handle": state.robot_handle,
        "message": f"Successfully connected to robot '{name}'"
    }
    
    state.log_operation("bcap_robot_connect", args, result)
    
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

async def handle_robot_takearm(args: dict) -> list[TextContent]:
    """Enable robot arm"""
    if not state.controller_handle:
        raise Exception("Please call bcap_controller_connect first")
    
    name = args.get("name", "Arm")
    option = args.get("option", "")

    state.client.robot_execute(state.robot_handle, "TakeArm", [0, 0])
    
    result = {
        "success": True,
        "robot_handle": state.robot_handle,
        "message": f"Successfully connected to robot '{name}'"
    }
    
    state.log_operation("bcap_robot_connect", args, result)
    
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

async def handle_robot_get_variable(args: dict) -> list[TextContent]:
    """Get robot variable value"""
    if not state.robot_handle:
        raise Exception("Please call bcap_robot_connect first")
    
    # Reading variables does not require TakeArm, read directly
    name = args["name"]
    option = args.get("option", "")

    
    
    var_handle = state.client.robot_getvariable(state.robot_handle, name, option)
    value = state.client.variable_getvalue(var_handle)
    state.client.variable_release(var_handle)
    
    result = {
        "success": True,
        "variable_name": name,
        "value": value
    }
    
    state.log_operation("bcap_robot_get_variable", args, result)
    
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

async def handle_robot_get_variable_names(args: dict) -> list[TextContent]:
    """Get robot variable name list"""
    if not state.robot_handle:
        raise Exception("Please call bcap_robot_connect first")
    
    # Reading variable name list does not require TakeArm, read directly
    option = args.get("option", "")
    variable_names = state.client.robot_getvariablenames(state.robot_handle, option)
    
    result = {
        "success": True,
        "variable_names": variable_names
    }
    
    state.log_operation("bcap_robot_get_variable_names", args, result)
    
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

async def handle_robot_move_to_joint_angles(args: dict) -> list[TextContent]:
    """Move robot to specified joint angles (create new BCAPClient/controller/robot instance each time, following read_joint_angles.py)"""
    import os
    import sys
    from bcapclient import BCAPClient

    host = state.connection_info.get("host", "192.168.0.1")
    port = state.connection_info.get("port", 5007)
    timeout = state.connection_info.get("timeout", 3.0)
    joint_angles = args["joint_angles"]
    option = args.get("option", "")

    # Fully follow read_joint_angles.py, complete flow each time
    client = BCAPClient(host, port, timeout)
    try:
        controller_handle = client.controller_connect(
            name="",
            provider="CaoProv.DENSO.VRC",
            machine="localhost",
            option=""
        )
        robot_handle = client.controller_getrobot(controller_handle, name="Arm", option="")
        # Get current angles
        var_handle = client.robot_getvariable(robot_handle, "@CURRENT_ANGLE", "")
        current_angles = client.variable_getvalue(var_handle)
        client.variable_release(var_handle)
        
        # Parse speed parameter from option (if present)
        speed_value = None
        if option and "Speed=" in option:
            try:
                # Extract numeric value from Speed=XX
                speed_str = option.split("Speed=")[1].split()[0].split(",")[0]
                speed_value = float(speed_str)
                logger.info(f"Parsed speed from option: {speed_value}%")
            except:
                pass
        
        # Execute motion
        client.robot_execute(robot_handle, "TakeArm", [0, 0])
        
        # If speed is specified, set speed first
        if speed_value is not None:
            try:
                client.robot_speed(robot_handle, 0, speed_value)  # 0 means all axes
                logger.info(f"Set robot speed to {speed_value}%")
            except Exception as e:
                logger.warning(f"Failed to set speed (may not be supported): {e}")
        
        client.robot_move(robot_handle, 1, [joint_angles, "J", "@E"], "")
        # Release resources
        client.robot_release(robot_handle)
        client.controller_disconnect(controller_handle)
        result = {
            "success": True,
            "previous_joint_angles": current_angles,
            "target_joint_angles": joint_angles,
            "message": "Robot motion command sent (following read_joint_angles.py single connection pattern)"
        }
    except Exception as e:
        result = {
            "success": False,
            "error": str(e)
        }
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

async def handle_robot_move_to_pose(args: dict) -> list[TextContent]:
    """Move robot to specified position and orientation"""
    if not state.robot_handle:
        raise Exception("Please call bcap_robot_connect first")
    
    pose = args["pose"]
    option = args.get("option", "")
    
    # Ensure 6 values [x, y, z, rx, ry, rz]
    if len(pose) != 6:
        raise ValueError("Position and orientation must be 6 values [x(mm), y(mm), z(mm), rx(deg), ry(deg), rz(deg)]")
    
    # Get current position (before TakeArm, consistent with read_joint_angles.py)
    var_handle = state.client.robot_getvariable(state.robot_handle, "@CURRENT_POSITION", "")
    current_pose = state.client.variable_getvalue(var_handle)
    state.client.variable_release(var_handle)
    
    # Execute TakeArm to enable robot motion (immediately before robot_move, consistent with read_joint_angles.py)
    state.client.robot_execute(state.robot_handle, "TakeArm", [0, 0])
    
    # Execute Cartesian space motion
    # robot_move(handle, comp, pose, option)
    # pose: [pose_list, "P", "@E"]
    # Note: If option is empty, use empty string
    move_option = option if option else ""
    state.client.robot_move(
        state.robot_handle,
        1,
        [pose, "P", "@E"],
        move_option
    )
    
    result = {
        "success": True,
        "message": "Robot motion command sent",
        "target_pose": pose,
        "previous_pose": current_pose,
        "warning": "Robot is moving, please wait for motion to complete and ensure safety"
    }
    
    state.log_operation("bcap_robot_move_to_pose", args, result)
    
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

async def handle_robot_gohome(args: dict) -> list[TextContent]:
    """Move robot back to home position"""
    if not state.robot_handle:
        raise Exception("Please call bcap_robot_connect first")
    
    # Get position before movement
    var_handle = state.client.robot_getvariable(state.robot_handle, "@CURRENT_ANGLE", "")
    current_angles = state.client.variable_getvalue(var_handle)
    state.client.variable_release(var_handle)
    
    # First execute GiveArm to release arm (if previously occupied)
    try:
        state.client.robot_execute(state.robot_handle, "GiveArm", None)
    except:
        pass  # If GiveArm fails (e.g., arm not occupied), continue
    
    # Execute TakeArm to enable robot motion
    state.client.robot_execute(state.robot_handle, "TakeArm", [0, 0])
    
    # Execute go home
    state.client.robot_gohome(state.robot_handle)
    
    result = {
        "success": True,
        "message": "Robot go home command sent",
        "previous_joint_angles": current_angles,
        "warning": "Robot is moving to home position, please wait for motion to complete"
    }
    
    state.log_operation("bcap_robot_gohome", args, result)
    
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

async def handle_robot_set_speed(args: dict) -> list[TextContent]:
    """Set robot motion speed"""
    if not state.robot_handle:
        raise Exception("Please call bcap_robot_connect first")
    
    # Setting speed does not require TakeArm, set directly
    
    axis = args.get("axis", 0)
    speed = args.get("speed", 50.0)
    
    # Set speed
    # robot_speed(handle, axis, speed)
    # axis: 0 means all axes, 1-6 means specific axis
    state.client.robot_speed(state.robot_handle, axis, speed)
    
    result = {
        "success": True,
        "message": f"Speed set successfully",
        "axis": axis,
        "speed": speed,
        "note": "Speed setting will affect subsequent motion commands"
    }
    
    state.log_operation("bcap_robot_set_speed", args, result)
    
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

async def handle_robot_execute_trajectory(args: dict) -> list[TextContent]:
    """Execute multiple joint angle motions in batch"""
    if not state.robot_handle:
        raise Exception("Please call bcap_robot_connect first")
    
    trajectory = args["trajectory"]
    option = args.get("option", "")
    
    # Validate trajectory points
    for i, point in enumerate(trajectory):
        if len(point) != 6:
            raise ValueError(f"Trajectory point {i+1} must have 6 joint angle values")
    
    # Get initial position
    initial_angles = None
    try:
        var_handle = state.client.robot_getvariable(state.robot_handle, "@CURRENT_ANGLE", "")
        initial_angles = state.client.variable_getvalue(var_handle)
        state.client.variable_release(var_handle)
        if isinstance(initial_angles, (list, tuple)):
            initial_angles = list(initial_angles)
    except Exception as e:
        logger.warning(f"Failed to get initial joint angles: {e}")
    
    # First execute GiveArm to release arm (if previously occupied)
    try:
        state.client.robot_execute(state.robot_handle, "GiveArm", None)
    except:
        pass  # If GiveArm fails (e.g., arm not occupied), continue
    
    # Execute TakeArm to enable robot motion (only once at trajectory start)
    state.client.robot_execute(state.robot_handle, "TakeArm", [0, 0])
    
    # Execute trajectory
    executed_points = []
    failed_points = []
    
    # Note: If option is empty, use empty string
    move_option = option if option else ""
    
    for i, joint_angles in enumerate(trajectory):
        try:
            # Execute joint space motion
            state.client.robot_move(
                state.robot_handle,
                1,
                [joint_angles, "J", "@E"],
                move_option
            )
            executed_points.append({
                "index": i + 1,
                "angles": joint_angles,
                "status": "success"
            })
            logger.info(f"Trajectory point {i+1}/{len(trajectory)} executed successfully: {joint_angles}")
        except Exception as e:
            error_msg = str(e)
            failed_points.append({
                "index": i + 1,
                "angles": joint_angles,
                "error": error_msg
            })
            logger.error(f"Trajectory point {i+1}/{len(trajectory)} execution failed: {error_msg}")
            # Optional: whether to continue on failure
            # Here we choose to continue, you can modify as needed
    
    result = {
        "success": len(failed_points) == 0,
        "message": f"Trajectory execution completed: {len(executed_points)}/{len(trajectory)} points successful",
        "total_points": len(trajectory),
        "executed_points": len(executed_points),
        "failed_points": len(failed_points),
        "initial_angles": initial_angles,
        "trajectory": trajectory,
        "executed_details": executed_points,
        "failed_details": failed_points if failed_points else None,
        "warning": "Robot has completed trajectory motion, please check final position"
    }
    
    state.log_operation("bcap_robot_execute_trajectory", args, result)
    
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

async def handle_robot_execute_slave_trajectory(args: dict) -> list[TextContent]:
    """Execute continuous trajectory motion using slave mode (smooth motion)"""
    if not state.robot_handle:
        raise Exception("Please call bcap_robot_connect first")
    
    trajectory = args["trajectory"]
    option = args.get("option", "")
    
    # Validate trajectory points
    for i, point in enumerate(trajectory):
        if len(point) != 6:
            raise ValueError(f"Trajectory point {i+1} must have 6 joint angle values")
    
    # Get initial position
    initial_angles = None
    try:
        var_handle = state.client.robot_getvariable(state.robot_handle, "@CURRENT_ANGLE", "")
        initial_angles = state.client.variable_getvalue(var_handle)
        state.client.variable_release(var_handle)
        if isinstance(initial_angles, (list, tuple)):
            initial_angles = list(initial_angles[:6])  # Only take first 6 joints
    except Exception as e:
        logger.warning(f"Failed to get initial joint angles: {e}")
    
    executed_points = []
    failed_points = []
    
    try:
        # First execute TakeArm to acquire control
        state.client.robot_execute(state.robot_handle, "TakeArm", [0, 0])
        
        # Enter slave mode (0x202)
        # According to DENSO official documentation, 0x202 means enable slave mode
        logger.info("Entering slave mode...")
        state.client.robot_execute(state.robot_handle, "slvChangeMode", 0x202)
        
        # Wait a short time to ensure mode switch completes
        time.sleep(0.1)
        
        # Send first trajectory point (initialization position)
        if len(trajectory) > 0:
            first_point = list(trajectory[0]) + [0, 0]  # slvMove requires 8 values
            try:
                state.client.robot_execute(state.robot_handle, "slvMove", first_point)
                executed_points.append({
                    "index": 1,
                    "angles": trajectory[0],
                    "status": "success"
                })
                logger.info(f"Trajectory point 1/{len(trajectory)} (initialization) sent successfully")
            except Exception as e:
                error_msg = str(e)
                failed_points.append({
                    "index": 1,
                    "angles": trajectory[0],
                    "error": error_msg
                })
                logger.error(f"Trajectory point 1/{len(trajectory)} (initialization) send failed: {error_msg}")
                raise
        
        # Loop to send all subsequent trajectory points
        for i in range(1, len(trajectory)):
            try:
                joint_angles = list(trajectory[i]) + [0, 0]  # slvMove requires 8 values
                state.client.robot_execute(state.robot_handle, "slvMove", joint_angles)
                executed_points.append({
                    "index": i + 1,
                    "angles": trajectory[i],
                    "status": "success"
                })
                logger.info(f"Trajectory point {i+1}/{len(trajectory)} sent successfully")
            except Exception as e:
                error_msg = str(e)
                failed_points.append({
                    "index": i + 1,
                    "angles": trajectory[i],
                    "error": error_msg
                })
                logger.error(f"Trajectory point {i+1}/{len(trajectory)} send failed: {error_msg}")
                # In slave mode, if a point fails, continue with subsequent points
        
        # Wait for trajectory execution to complete
        time.sleep(0.1)
        
        # Exit slave mode (0x000)
        logger.info("Exiting slave mode...")
        state.client.robot_execute(state.robot_handle, "slvChangeMode", 0x000)
        
        # Release control
        time.sleep(0.1)
        state.client.robot_execute(state.robot_handle, "GiveArm", None)
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Slave mode trajectory execution exception: {error_msg}")
        
        # Try to exit slave mode and release control
        try:
            state.client.robot_execute(state.robot_handle, "slvChangeMode", 0x000)
            state.client.robot_execute(state.robot_handle, "GiveArm", None)
        except:
            pass
        
        result = {
            "success": False,
            "message": f"Trajectory execution failed: {error_msg}",
            "total_points": len(trajectory),
            "executed_points": len(executed_points),
            "failed_points": len(failed_points),
            "initial_angles": initial_angles,
            "error": error_msg
        }
        state.log_operation("bcap_robot_execute_slave_trajectory", args, result)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
    
    result = {
        "success": len(failed_points) == 0,
        "message": f"Slave mode trajectory execution completed: {len(executed_points)}/{len(trajectory)} points successful",
        "total_points": len(trajectory),
        "executed_points": len(executed_points),
        "failed_points": len(failed_points),
        "initial_angles": initial_angles,
        "trajectory": trajectory,
        "executed_details": executed_points,
        "failed_details": failed_points if failed_points else None,
        "mode": "slave_mode",
        "warning": "Robot has completed slave mode trajectory motion, please check final position"
    }
    
    state.log_operation("bcap_robot_execute_slave_trajectory", args, result)
    
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

async def handle_robot_open_gripper(args: dict) -> list[TextContent]:
    """Open robot gripper (fully following cobotta_x_RIKEN.py line 169-175)"""
    if not state.controller_handle:
        raise Exception("Please call bcap_controller_connect first")
    
    dist = args.get("dist", 0.030)  # Default 30mm (maximum open)
    speed = args.get("speed", 100)
    
    # Validate distance range (reference cobotta_x_RIKEN.py line 174)
    if not (0 <= dist <= 0.03):
        raise ValueError("Distance must be between 0 and 0.03 meters")
    
    # Execute exactly as cobotta_x_RIKEN.py line 175
    # self.bcc.controller_execute(self.hctrl, "HandMoveA", [dist * 1000, speed])
    state.client.controller_execute(state.controller_handle, "HandMoveA", [dist * 1000, speed])
    
    result = {
        "success": True,
        "message": f"Gripper opened to {dist*1000:.1f}mm",
        "action": "open_gripper",
        "distance_mm": dist * 1000,
        "speed": speed,
        "note": "Use HandMoveA command to open gripper (fully following cobotta_x_RIKEN.py)"
    }
    
    state.log_operation("bcap_robot_open_gripper", args, result)
    
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

async def handle_robot_close_gripper(args: dict) -> list[TextContent]:
    """Close robot gripper (fully following cobotta_x_RIKEN.py line 177-183)"""
    if not state.controller_handle:
        raise Exception("Please call bcap_controller_connect first")
    
    dist = args.get("dist", 0.0)  # Default 0mm (fully closed)
    speed = args.get("speed", 20)
    
    # Validate distance range (reference cobotta_x_RIKEN.py line 182)
    if not (0 <= dist <= 0.03):
        raise ValueError("Distance must be between 0 and 0.03 meters")
    
    # Execute exactly as cobotta_x_RIKEN.py line 183
    # self.bcc.controller_execute(self.hctrl, "HandMoveA", [dist * 1000, speed])
    state.client.controller_execute(state.controller_handle, "HandMoveA", [dist * 1000, speed])
    
    result = {
        "success": True,
        "message": f"Gripper closed to {dist*1000:.1f}mm",
        "action": "close_gripper",
        "distance_mm": dist * 1000,
        "speed": speed,
        "note": "Use HandMoveA command to close gripper (fully following cobotta_x_RIKEN.py)"
    }
    
    state.log_operation("bcap_robot_close_gripper", args, result)
    
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

async def handle_robot_pick_and_place(args: dict) -> list[TextContent]:
    """Execute complete pick-and-place operation sequence"""
    if not state.controller_handle:
        raise Exception("Please call bcap_controller_connect first")
    if not state.robot_handle:
        raise Exception("Please call bcap_robot_connect first")
    
    # Get parameters (unit: cm)
    pick_down_distance = args.get("pick_down_distance", 4.0)  # cm
    lift_up_distance = args.get("lift_up_distance", 9.0)  # cm
    place_y_offset = args.get("place_y_offset", 2.5)  # cm
    place_down_distance = args.get("place_down_distance", 3.0)  # cm
    gripper_speed = args.get("gripper_speed", 100)
    
    # Convert to millimeters
    pick_down_mm = pick_down_distance * 10
    lift_up_mm = lift_up_distance * 10
    place_y_mm = place_y_offset * 10
    place_down_mm = place_down_distance * 10
    
    # Record operation steps
    steps = []
    errors = []
    
    try:
        # Get initial position
        var_handle = state.client.robot_getvariable(state.robot_handle, "@CURRENT_POSITION", "")
        initial_pose = state.client.variable_getvalue(var_handle)
        state.client.variable_release(var_handle)
        
        x, y, z = initial_pose[0], initial_pose[1], initial_pose[2]
        rx, ry, rz = initial_pose[3], initial_pose[4], initial_pose[5]
        
        steps.append({
            "step": 0,
            "action": "get_initial_position",
            "position": [x, y, z, rx, ry, rz],
            "status": "success"
        })
        
        # Step 1: Open gripper (prepare for picking)
        try:
            state.client.controller_execute(state.controller_handle, "HandMoveA", [30.0, gripper_speed])
            steps.append({
                "step": 1,
                "action": "open_gripper",
                "gripper_distance_mm": 30.0,
                "speed": gripper_speed,
                "status": "success"
            })
            time.sleep(0.3)
        except Exception as e:
            error_msg = f"Step 1 failed (may be simulator limitation): {str(e)}"
            errors.append(error_msg)
            steps.append({"step": 1, "action": "open_gripper", "status": "failed", "error": error_msg})
        
        # Step 2: Move down to pick position
        try:
            state.client.robot_execute(state.robot_handle, "TakeArm", [0, 0])
            pick_z = z - pick_down_mm
            state.client.robot_move(state.robot_handle, 1, [[x, y, pick_z, rx, ry, rz], "P", "@E"], "")
            steps.append({
                "step": 2,
                "action": "move_down_to_pick",
                "distance_mm": pick_down_mm,
                "position": [x, y, pick_z, rx, ry, rz],
                "status": "success"
            })
            time.sleep(0.5)  # Wait for motion to complete
        except Exception as e:
            error_msg = f"Step 2 failed: {str(e)}"
            errors.append(error_msg)
            steps.append({"step": 2, "action": "move_down_to_pick", "status": "failed", "error": error_msg})
        
        # Step 3: Close gripper (close to 21mm)
        try:
            state.client.controller_execute(state.controller_handle, "HandMoveA", [21.0, gripper_speed])
            steps.append({
                "step": 3,
                "action": "close_gripper",
                "gripper_distance_mm": 21.0,
                "speed": gripper_speed,
                "status": "success"
            })
            time.sleep(0.3)
        except Exception as e:
            error_msg = f"Step 3 failed (may be simulator limitation): {str(e)}"
            errors.append(error_msg)
            steps.append({"step": 3, "action": "close_gripper", "status": "failed", "error": error_msg})
        
        # Steps 4-6: Lift up (3 times, 1/3 distance each)
        step_up_mm = lift_up_mm / 3
        current_z = pick_z
        for i in range(3):
            try:
                state.client.robot_execute(state.robot_handle, "TakeArm", [0, 0])
                current_z += step_up_mm
                state.client.robot_move(state.robot_handle, 1, [[x, y, current_z, rx, ry, rz], "P", "@E"], "")
                steps.append({
                    "step": 4 + i,
                    "action": f"lift_up_{i+1}",
                    "distance_mm": step_up_mm,
                    "position": [x, y, current_z, rx, ry, rz],
                    "status": "success"
                })
                time.sleep(0.3)
            except Exception as e:
                error_msg = f"Step {4+i} failed: {str(e)}"
                errors.append(error_msg)
                steps.append({"step": 4+i, "action": f"lift_up_{i+1}", "status": "failed", "error": error_msg})
        
        # Step 7: Move along Y-axis to place position
        try:
            state.client.robot_execute(state.robot_handle, "TakeArm", [0, 0])
            place_y = y + place_y_mm
            state.client.robot_move(state.robot_handle, 1, [[x, place_y, current_z, rx, ry, rz], "P", "@E"], "")
            steps.append({
                "step": 7,
                "action": "move_y_to_place",
                "distance_mm": place_y_mm,
                "position": [x, place_y, current_z, rx, ry, rz],
                "status": "success"
            })
            time.sleep(0.5)
        except Exception as e:
            error_msg = f"Step 7 failed: {str(e)}"
            errors.append(error_msg)
            steps.append({"step": 7, "action": "move_y_to_place", "status": "failed", "error": error_msg})
        
        # Step 8: Move down to place position
        try:
            state.client.robot_execute(state.robot_handle, "TakeArm", [0, 0])
            place_z = current_z - place_down_mm
            state.client.robot_move(state.robot_handle, 1, [[x, place_y, place_z, rx, ry, rz], "P", "@E"], "")
            steps.append({
                "step": 8,
                "action": "move_down_to_place",
                "distance_mm": place_down_mm,
                "position": [x, place_y, place_z, rx, ry, rz],
                "status": "success"
            })
            time.sleep(0.5)
        except Exception as e:
            error_msg = f"Step 8 failed: {str(e)}"
            errors.append(error_msg)
            steps.append({"step": 8, "action": "move_down_to_place", "status": "failed", "error": error_msg})
        
        # Step 9: Open gripper
        try:
            state.client.controller_execute(state.controller_handle, "HandMoveA", [30.0, gripper_speed])
            steps.append({
                "step": 9,
                "action": "open_gripper",
                "gripper_distance_mm": 30.0,
                "speed": gripper_speed,
                "status": "success"
            })
            time.sleep(0.3)
        except Exception as e:
            error_msg = f"Step 9 failed (may be simulator limitation): {str(e)}"
            errors.append(error_msg)
            steps.append({"step": 9, "action": "open_gripper", "status": "failed", "error": error_msg})
        
        # Step 10: Return to initial position
        try:
            state.client.robot_execute(state.robot_handle, "TakeArm", [0, 0])
            state.client.robot_move(state.robot_handle, 1, [[x, y, z, rx, ry, rz], "P", "@E"], "")
            steps.append({
                "step": 10,
                "action": "return_to_initial_position",
                "position": [x, y, z, rx, ry, rz],
                "status": "success"
            })
            time.sleep(0.5)
        except Exception as e:
            error_msg = f"Step 10 failed: {str(e)}"
            errors.append(error_msg)
            steps.append({"step": 10, "action": "return_to_initial_position", "status": "failed", "error": error_msg})
        
        # Get final position
        var_handle = state.client.robot_getvariable(state.robot_handle, "@CURRENT_POSITION", "")
        final_pose = state.client.variable_getvalue(var_handle)
        state.client.variable_release(var_handle)
        
        result = {
            "success": len(errors) == 0,
            "message": f"Pick-and-place operation completed: {len(steps)} steps (including initial position record), {len(errors)} errors",
            "initial_position": initial_pose[:6],
            "final_position": final_pose[:6],
            "parameters": {
                "pick_down_distance_cm": pick_down_distance,
                "lift_up_distance_cm": lift_up_distance,
                "place_y_offset_cm": place_y_offset,
                "place_down_distance_cm": place_down_distance,
                "gripper_speed": gripper_speed
            },
            "steps": steps,
            "errors": errors if errors else None,
            "warning": "Robot has completed pick-and-place operation, please check final position"
        }
        
    except Exception as e:
        result = {
            "success": False,
            "message": f"Pick-and-place operation failed: {str(e)}",
            "error": str(e),
            "steps": steps,
            "errors": errors
        }
    
    state.log_operation("bcap_robot_pick_and_place", args, result)
    
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

async def handle_get_operation_log(args: dict) -> list[TextContent]:
    """Get operation log"""
    limit = args.get("limit", 50)
    logs = state.operation_log[-limit:]
    
    result = {
        "success": True,
        "total_operations": len(state.operation_log),
        "returned_count": len(logs),
        "logs": logs
    }
    
    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

# ============================================================================
# Helper functions
# ============================================================================

def get_error_description(hresult: int) -> str:
    """Get error code description"""
    error_map = {
        HResult.E_TIMEOUT: "Connection timeout",
        HResult.E_NOT_CONNECTED: "Not connected",
        HResult.E_ACCESSDENIED: "Access denied",
        HResult.E_INVALIDARG: "Invalid parameter",
        HResult.E_CAO_OBJECT_NOTFOUND: "Object not found",
        HResult.E_CAO_VARIANT_TYPE_NOSUPPORT: "Unsupported variable type",
        HResult.E_FAIL: "Operation failed",
    }
    return error_map.get(hresult, f"Unknown error ({hresult})")

# ============================================================================
# Main function
# ============================================================================

async def main():
    """Run MCP Server"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())


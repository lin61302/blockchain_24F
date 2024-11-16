// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";

contract Source is AccessControl {
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    bytes32 public constant WARDEN_ROLE = keccak256("BRIDGE_WARDEN_ROLE");
	mapping( address => bool) public approved;
	address[] public tokens;

	event Deposit( address indexed token, address indexed recipient, uint256 amount );
	event Withdrawal( address indexed token, address indexed recipient, uint256 amount );
	event Registration( address indexed token );

    constructor( address admin ) {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(ADMIN_ROLE, admin);
        _grantRole(WARDEN_ROLE, admin);

    }

	function deposit(address _token, address _recipient, uint256 _amount ) public {
		//YOUR CODE HERE
		require(approved[_token], "Token is not registered");
    require(_recipient != address(0), "Invalid recipient address");
    require(_amount > 0, "Amount must be greater than zero");

    // Interface to interact with the ERC20 token
    IERC20 token = IERC20(_token);

    // Transfer tokens from the sender to this contract
    require(
        token.transferFrom(msg.sender, address(this), _amount),
        "Token transfer failed"
    );

    // Emit the Deposit event
    emit Deposit(_token, _recipient, _amount);
	}

	function withdraw(address _token, address _recipient, uint256 _amount ) onlyRole(WARDEN_ROLE) public {
		//YOUR CODE HERE
		require(approved[_token], "Token is not registered");
    require(_recipient != address(0), "Invalid recipient address");
    require(_amount > 0, "Amount must be greater than zero");

    // Interface to interact with the ERC20 token
    IERC20 token = IERC20(_token);

    // Transfer tokens from this contract to the recipient
    require(
        token.transfer(_recipient, _amount),
        "Token transfer failed"
    );

    // Emit the Withdrawal event
    emit Withdrawal(_token, _recipient, _amount);
	}

	function registerToken(address _token) onlyRole(ADMIN_ROLE) public {
		//YOUR CODE HERE
		require(_token != address(0), "Invalid token address");
    require(!approved[_token], "Token is already registered");

    // Mark the token as approved
    approved[_token] = true;

    // Add the token to the list of registered tokens
    tokens.push(_token);

    // Emit the Registration event
    emit Registration(_token);
	}


}

// SPDX-License-Identifier: MIT
pragma solidity ^0.8.17;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "./BridgeToken.sol";

/**
 * @title Destination
 * @dev Contract that manages the creation, wrapping, and unwrapping of BridgeTokens.
 */
contract Destination is AccessControl {
    // Define roles using keccak256 hash of role names
    bytes32 public constant WARDEN_ROLE = keccak256("BRIDGE_WARDEN_ROLE");
    bytes32 public constant CREATOR_ROLE = keccak256("CREATOR_ROLE");

    // Mapping from underlying token address to wrapped token address
    mapping(address => address) public wrapped_tokens;

    // Mapping from wrapped token address to underlying token address
    mapping(address => address) public underlying_tokens;

    // Array to keep track of all registered underlying tokens
    address[] public tokens;

    // Events
    event Creation(address indexed underlying_token, address indexed wrapped_token);
    event Wrap(
        address indexed underlying_token,
        address indexed wrapped_token,
        address indexed to,
        uint256 amount
    );
    event Unwrap(
        address indexed underlying_token,
        address indexed wrapped_token,
        address frm,
        address indexed to,
        uint256 amount
    );

    /**
     * @dev Constructor that sets up roles.
     * @param admin The address that will have DEFAULT_ADMIN_ROLE, CREATOR_ROLE, and WARDEN_ROLE.
     */
    constructor(address admin) {
        require(admin != address(0), "Admin address cannot be zero");

        // Grant DEFAULT_ADMIN_ROLE, CREATOR_ROLE, and WARDEN_ROLE to the admin
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(CREATOR_ROLE, admin);
        _grantRole(WARDEN_ROLE, admin);
    }

    /**
     * @dev Creates a new BridgeToken for a given underlying token.
     * Can only be called by accounts with CREATOR_ROLE.
     * @param _underlying_token The address of the underlying token on the source chain.
     * @param name The name of the underlying token.
     * @param symbol The symbol of the underlying token.
     * @return The address of the newly created BridgeToken.
     */
    function createToken(
        address _underlying_token,
        string memory name,
        string memory symbol
    ) public onlyRole(CREATOR_ROLE) returns (address) {
        require(_underlying_token != address(0), "Invalid underlying token address");
        require(
            wrapped_tokens[_underlying_token] == address(0),
            "BridgeToken already exists for this underlying token"
        );

        // Deploy a new BridgeToken contract, setting Destination as admin
        BridgeToken bridgeToken = new BridgeToken(
            _underlying_token,
            name,
            symbol,
            address(this)
        );

        // Store mappings correctly:
        // Map underlying_token to bridgeToken
        wrapped_tokens[_underlying_token] = address(bridgeToken);
        // Map bridgeToken to underlying_token
        underlying_tokens[address(bridgeToken)] = _underlying_token;

        // Add to tokens array
        tokens.push(_underlying_token);

        // Emit Creation event with the actual bridgeToken address
        emit Creation(_underlying_token, address(bridgeToken));

        return address(bridgeToken);
    }

    /**
     * @dev Mints BridgeTokens to a recipient.
     * Can only be called by accounts with WARDEN_ROLE.
     * @param _underlying_token The address of the underlying token on the source chain.
     * @param _recipient The address to receive the minted BridgeTokens.
     * @param _amount The amount of tokens to mint.
     */
    function wrap(
        address _underlying_token,
        address _recipient,
        uint256 _amount
    ) public onlyRole(WARDEN_ROLE) {
        require(_underlying_token != address(0), "Invalid underlying token address");
        require(_recipient != address(0), "Invalid recipient address");
        require(_amount > 0, "Amount must be greater than zero");
        require(
            wrapped_tokens[_underlying_token] != address(0),
            "Underlying token not registered"
        );

        // Get the wrapped token address
        address wrappedTokenAddress = wrapped_tokens[_underlying_token];
        BridgeToken wrappedToken = BridgeToken(wrappedTokenAddress);

        // Mint BridgeTokens to the recipient
        wrappedToken.mint(_recipient, _amount);

        // Emit Wrap event
        emit Wrap(_underlying_token, wrappedTokenAddress, _recipient, _amount);
    }

    /**
     * @dev Burns BridgeTokens from the caller and initiates the unwrap process.
     * Anyone can call this function, but only tokens they own can be burned.
     * @param _wrapped_token The address of the BridgeToken being unwrapped.
     * @param _recipient The address to receive the underlying tokens on the source chain.
     * @param _amount The amount of tokens to burn and unwrap.
     */
    function unwrap(
        address _wrapped_token,
        address _recipient,
        uint256 _amount
    ) public {
        require(_wrapped_token != address(0), "Invalid BridgeToken address");
        require(_recipient != address(0), "Invalid recipient address");
        require(_amount > 0, "Amount must be greater than zero");

        // Verify that the wrapped token is recognized and mapped to an underlying token
        require(
            underlying_tokens[_wrapped_token] != address(0),
            "Wrapped token not recognized"
        );

        // Get the underlying token address
        address underlyingTokenAddress = underlying_tokens[_wrapped_token];

        // Instantiate the BridgeToken contract
        BridgeToken wrappedToken = BridgeToken(_wrapped_token);

        // Burn the BridgeTokens from the caller using burnFrom
        wrappedToken.burnFrom(msg.sender, _amount);

        // Emit Unwrap event
        emit Unwrap(underlyingTokenAddress, _wrapped_token, msg.sender, _recipient, _amount);

        // Note: Actual transfer of underlying tokens back to the recipient on the source chain
        // Typically handled off-chain or via cross-chain messaging protocols
    }

    /**
     * @dev Returns the number of registered underlying tokens.
     * @return The count of underlying tokens.
     */
    function getTokenCount() public view returns (uint256) {
        return tokens.length;
    }

    /**
     * @dev Returns the underlying token at a specific index in the tokens array.
     * @param index The index in the tokens array.
     * @return The address of the underlying token.
     */
    function getUnderlyingToken(uint256 index) public view returns (address) {
        require(index < tokens.length, "Index out of bounds");
        return tokens[index];
    }
}

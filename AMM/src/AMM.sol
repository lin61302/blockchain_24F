// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.17;

import "@openzeppelin/contracts/access/AccessControl.sol"; //This allows role-based access control through _grantRole() and the modifier onlyRole
import "@openzeppelin/contracts/token/ERC20/ERC20.sol"; //This contract needs to interact with ERC20 tokens

contract AMM is AccessControl{
    bytes32 public constant LP_ROLE = keccak256("LP_ROLE");
	uint256 public invariant;
	address public tokenA;
	address public tokenB;
	uint256 feebps = 3; //The fee in basis points (i.e., the fee should be feebps/10000)

	event Swap( address indexed _inToken, address indexed _outToken, uint256 inAmt, uint256 outAmt );
	event LiquidityProvision( address indexed _from, uint256 AQty, uint256 BQty );
	event Withdrawal( address indexed _from, address indexed recipient, uint256 AQty, uint256 BQty );

	/*
		Constructor sets the addresses of the two tokens
	*/
    constructor( address _tokenA, address _tokenB ) {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender );
        _grantRole(LP_ROLE, msg.sender);

		require( _tokenA != address(0), 'Token address cannot be 0' );
		require( _tokenB != address(0), 'Token address cannot be 0' );
		require( _tokenA != _tokenB, 'Tokens cannot be the same' );
		tokenA = _tokenA;
		tokenB = _tokenB;

    }


	function getTokenAddress( uint256 index ) public view returns(address) {
		require( index < 2, 'Only two tokens' );
		if( index == 0 ) {
			return tokenA;
		} else {
			return tokenB;
		}
	}

	/*
		The main trading functions
		
		User provides sellToken and sellAmount

		The contract must calculate buyAmount using the formula:
	*/
	function tradeTokens( address sellToken, uint256 sellAmount ) public {
		require( invariant > 0, 'Invariant must be nonzero' );
		require( sellToken == tokenA || sellToken == tokenB, 'Invalid token' );
		require( sellAmount > 0, 'Cannot trade 0' );
		require( invariant > 0, 'No liquidity' );
		uint256 qtyA;
		uint256 qtyB;
		uint256 swapAmt;

		//YOUR CODE HERE 
    
    
		address buyToken;
		uint256 buyAmount;
		
		// Determine which token is being bought
		if (sellToken == tokenA) {
		    buyToken = tokenB;
		} else {
		    buyToken = tokenA;
		}
		
		// Transfer sellToken from the trader to the AMM contract
		bool successSell = ERC20(sellToken).transferFrom(msg.sender, address(this), sellAmount);
		require(successSell, "Transfer of sellToken failed");
		
		// Calculate the effective sell amount after applying the fee
		uint256 effectiveSellAmount = (sellAmount * (10000 - feebps)) / 10000;
		
		// Fetch updated reserves after the sellToken has been transferred
		uint256 reserveA = ERC20(tokenA).balanceOf(address(this));
		uint256 reserveB = ERC20(tokenB).balanceOf(address(this));
		
		if (sellToken == tokenA) {
		    // Calculate buyAmount using the invariant: k = (Ai + ΔA') * (Bi - ΔB)
		    buyAmount = reserveB - (invariant / (reserveA + effectiveSellAmount));
		} else {
		    // Calculate buyAmount using the invariant: k = (Ai - ΔB') * (Bi + ΔB')
		    buyAmount = reserveA - (invariant / (reserveB + effectiveSellAmount));
		}
		
		// Ensure that the AMM has enough tokens to fulfill the trade
		require(buyAmount > 0, "Insufficient output amount");
		
		// Transfer buyAmount of the other token to the trader
		bool successBuy = ERC20(buyToken).transfer(msg.sender, buyAmount);
		require(successBuy, "Transfer of buyToken failed");
		
		// Emit the Swap event
		emit Swap(sellToken, buyToken, sellAmount, buyAmount);
		
		// Update the invariant
		uint256 newReserveA = ERC20(tokenA).balanceOf(address(this));
		uint256 newReserveB = ERC20(tokenB).balanceOf(address(this));
		uint256 newInvariant = newReserveA * newReserveB;
		
		require(newInvariant >= invariant, "Invariant violation after trade");
		invariant = newInvariant;}
    

	// 	uint256 new_invariant = ERC20(tokenA).balanceOf(address(this))*ERC20(tokenB).balanceOf(address(this));
	// 	require( new_invariant >= invariant, 'Bad trade' );
	// 	invariant = new_invariant;
	// }

	/*
		Use the ERC20 transferFrom to "pull" amtA of tokenA and amtB of tokenB from the sender
	*/
	function provideLiquidity( uint256 amtA, uint256 amtB ) public {
		require( amtA > 0 || amtB > 0, 'Cannot provide 0 liquidity' );
		//YOUR CODE HERE
    // Transfer tokenA from the sender to the AMM contract
    if (amtA > 0) {
        bool successA = ERC20(tokenA).transferFrom(msg.sender, address(this), amtA);
        require(successA, "Transfer of Token A failed");
    }

    // Transfer tokenB from the sender to the AMM contract
    if (amtB > 0) {
        bool successB = ERC20(tokenB).transferFrom(msg.sender, address(this), amtB);
        require(successB, "Transfer of Token B failed");
    }

    // If this is the first liquidity provision, set the invariant
    if (invariant == 0) {
        invariant = amtA * amtB;
    } else {
        // Ensure that the liquidity is added in the correct ratio to maintain the invariant
        uint256 currentA = ERC20(tokenA).balanceOf(address(this));
        uint256 currentB = ERC20(tokenB).balanceOf(address(this));
        require(currentA * amtB == currentB * amtA, "Invariant not maintained");
    }
    
		emit LiquidityProvision( msg.sender, amtA, amtB );
	}

	/*
		Use the ERC20 transfer function to send amtA of tokenA and amtB of tokenB to the target recipient
		The modifier onlyRole(LP_ROLE) 
	*/
	function withdrawLiquidity( address recipient, uint256 amtA, uint256 amtB ) public onlyRole(LP_ROLE) {
		require( amtA > 0 || amtB > 0, 'Cannot withdraw 0' );
		require( recipient != address(0), 'Cannot withdraw to 0 address' );
		if( amtA > 0 ) {
			ERC20(tokenA).transfer(recipient,amtA);
		}
		if( amtB > 0 ) {
			ERC20(tokenB).transfer(recipient,amtB);
		}
		invariant = ERC20(tokenA).balanceOf(address(this))*ERC20(tokenB).balanceOf(address(this));
		emit Withdrawal( msg.sender, recipient, amtA, amtB );
	}


}

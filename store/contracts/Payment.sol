// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * One contract per order: payment + delivery (per IEP spec).
 * - Price in wei = order_price * 100. Only the bound customer can pay.
 * - After delivery confirmation: 80% to owner, 20% to courier; no further interaction.
 */
contract Payment {
    address public owner;

    struct OrderInfo {
        uint256 priceWei;
        address customer;
        bool initialized;
        bool paid;
        bool pickedUp;
        bool delivered;
        bool closed;
        address courier;
    }

    OrderInfo private order;

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }

    modifier whenNotClosed() {
        require(!order.closed, "Closed");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    /// One-time setup: set price and bind customer for this order.
    function initialize(uint256 priceWei, address customer_) external onlyOwner whenNotClosed {
        require(priceWei > 0, "Bad price");
        require(customer_ != address(0), "Bad customer");
        require(!order.initialized, "Exists");
        order = OrderInfo({
            priceWei: priceWei,
            customer: customer_,
            initialized: true,
            paid: false,
            pickedUp: false,
            delivered: false,
            closed: false,
            courier: address(0)
        });
    }

    function isPaid() external view returns (bool) {
        return order.paid;
    }

    /// Only the customer bound to this contract can pay; must send exact priceWei.
    function pay() external payable whenNotClosed {
        require(order.initialized, "Unknown");
        require(msg.sender == order.customer, "Not customer");
        require(!order.paid, "Already paid");
        require(msg.value == order.priceWei, "Wrong amount");
        order.paid = true;
    }

    function pickUp(address courier) external onlyOwner whenNotClosed {
        require(order.initialized, "Unknown");
        require(order.paid, "Not paid");
        require(!order.pickedUp, "Already picked");
        require(courier != address(0), "Bad courier");
        order.pickedUp = true;
        order.courier = courier;
    }

    /// On delivery: 80% to owner, 20% to courier; then forbid further interaction.
    function deliver() external onlyOwner whenNotClosed {
        require(order.initialized, "Unknown");
        require(order.pickedUp, "Not picked");
        require(!order.delivered, "Already delivered");
        order.delivered = true;
        order.closed = true;

        uint256 balance = address(this).balance;
        require(balance > 0, "No balance");
        uint256 toOwner = (balance * 80) / 100;
        uint256 toCourier = balance - toOwner;

        (bool okOwner,) = payable(owner).call{value: toOwner}("");
        require(okOwner, "Transfer owner failed");
        (bool okCourier,) = payable(order.courier).call{value: toCourier}("");
        require(okCourier, "Transfer courier failed");
    }
}

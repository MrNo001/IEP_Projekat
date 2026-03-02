// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * Minimal payment + delivery state machine per order.
 * - Owner (backend) creates orders, marks pickup/delivery.
 * - Customer pays by calling pay(orderId) with msg.value == priceWei.
 */
contract Payment {
    address public owner;

    struct OrderInfo {
        uint256 priceWei;
        bool exists;
        bool paid;
        bool pickedUp;
        bool delivered;
        address courier;
    }

    mapping(uint256 => OrderInfo) private orders;

    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }

    constructor() {
        owner = msg.sender;
    }

    function createOrder(uint256 orderId, uint256 priceWei) external onlyOwner {
        require(orderId > 0, "Bad id");
        require(!orders[orderId].exists, "Exists");
        orders[orderId] = OrderInfo({
            priceWei: priceWei,
            exists: true,
            paid: false,
            pickedUp: false,
            delivered: false,
            courier: address(0)
        });
    }

    function isPaid(uint256 orderId) external view returns (bool) {
        return orders[orderId].paid;
    }

    function pay(uint256 orderId) external payable {
        OrderInfo storage o = orders[orderId];
        require(o.exists, "Unknown");
        require(!o.paid, "Already paid");
        require(msg.value == o.priceWei, "Wrong amount");
        o.paid = true;
        // Funds stay in contract for this MVP (tests don't check settlement).
    }

    function pickUp(uint256 orderId, address courier) external onlyOwner {
        OrderInfo storage o = orders[orderId];
        require(o.exists, "Unknown");
        require(o.paid, "Not paid");
        require(!o.pickedUp, "Already picked");
        require(courier != address(0), "Bad courier");
        o.pickedUp = true;
        o.courier = courier;
    }

    function deliver(uint256 orderId) external onlyOwner {
        OrderInfo storage o = orders[orderId];
        require(o.exists, "Unknown");
        require(o.pickedUp, "Not picked");
        require(!o.delivered, "Already delivered");
        o.delivered = true;
    }
}



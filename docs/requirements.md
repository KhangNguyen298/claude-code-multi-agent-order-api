# Requirements: Order Management API

## Entities
- **Customer**: id, name, email (unique)
- **Product**: id, name, price, stock
- **Order**: id, customer, list of items, status, total, created_at
- **OrderItem**: product, quantity, unit price at time of order

## Features
1. CRUD for products (create, list, get by id, update, delete).
2. Create a customer, get a customer.
3. Create an order with one or more items:
   - quantity must be > 0
   - product must exist and have enough stock
   - stock is reduced when the order is created
   - total is calculated by the server, never sent by the client
4. List orders (filter by status and customer), get order by id.
5. Change order status. Allowed transitions only:
   PENDING -> PAID -> SHIPPED -> DELIVERED
   PENDING or PAID -> CANCELLED (stock is returned when cancelled)
6. All errors use one JSON format: `{"error": {"code": "...", "message": "..."}}`

## Out of scope
- Authentication, payments, frontend.

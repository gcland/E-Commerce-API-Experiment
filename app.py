from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
import pymysql
pymysql.install_as_MySQLdb()
from datetime import datetime
from marshmallow import fields, validate
from marshmallow import ValidationError
from sqlalchemy import select
from password import password


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql://root:{password}@localhost/e_commerce_db_exp'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)
ma = Marshmallow(app)

# Customer Model
class Customer(db.Model):
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    
    def to_dict(self):
        """Convert Customer object to dictionary for JSON serialization""" # Similar to using schemas
        return {
            'id': self.id,
            'name': self.name
        }
    
class Product(db.Model):
    __tablename__ = 'products'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    
    def to_dict(self):
        """Convert Product object to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'stock': self.stock
        }

# Order - Product Association Table
order_products = db.Table('order_products',
    db.Column('order_id', db.Integer, db.ForeignKey('orders.id'), primary_key=True),
    db.Column('product_id', db.Integer, db.ForeignKey('products.id'), primary_key=True),
    db.Column('quantity', db.Integer, nullable=False, default=1)
)

# Order Model
class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    delivery_date = db.Column(db.DateTime, nullable=True)
    order_total = db.Column(db.Float, nullable=False, default=0.0)  # New field
    
    # Relationship to Customer (Many Orders to One Customer)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    customer = db.relationship('Customer', backref=db.backref('orders', lazy=True))
    
    # Many-to-Many relationship with Products through order_products association table
    products = db.relationship('Product', secondary=order_products, 
        backref=db.backref('orders', lazy='dynamic'),
        lazy='dynamic')
    
    def to_dict(self):
        """Convert Order object to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'order_date': self.order_date.isoformat() if self.order_date else None,
            'delivery_date': self.delivery_date.isoformat() if self.delivery_date else None,
            'customer_id': self.customer_id,
            'order_total': self.order_total,  # Add order total to the dictionary
            'products': [
                {
                    'product_id': assoc.id, 
                    'name': assoc.name, 
                    'price': assoc.price,
                    'quantity': db.session.query(order_products.c.quantity)
                        .filter(order_products.c.order_id == self.id)
                        .filter(order_products.c.product_id == assoc.id)
                        .scalar()
                } for assoc in self.products
            ]
        }

# Create tables (run this once to set up database)
with app.app_context():
    db.create_all()

# Endpoint to add a new customer
# Example input:

# {
#     "name": "Grant"
# }
@app.route('/customers', methods=['POST'])
def add_customer():
    # Get data from request
    data = request.get_json()
    
    # Validate input
    if not data or 'name' not in data:
        return jsonify({"error": "Name is required"}), 400
    
    # Create new customer
    new_customer = Customer(name=data['name'])
    
    try:
        # Add and commit to database
        db.session.add(new_customer)
        db.session.commit()
        
        # Return the created customer
        return jsonify(new_customer.to_dict()), 201
    except Exception as e:
        # Rollback in case of error
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# Endpoint to get all customers
@app.route('/customers', methods=['GET'])
def get_customers():
    try:
        # Query all customers
        customers = Customer.query.all()
        
        # Convert to list of dictionaries
        customers_list = [customer.to_dict() for customer in customers]
        
        return jsonify(customers_list), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
# Endpoint to add a new product
# Example input: 

# {
#     "name": "Cable",
#     "description": "bbb",
#     "price": 19.99,
#     "stock": 100
# }
@app.route('/products', methods=['POST'])
def add_product():
    # Get data from request
    data = request.get_json()
    
    # Validate input
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    # Check required fields
    required_fields = ['name', 'price', 'stock']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"{field.capitalize()} is required"}), 400
    
    # Create new product
    new_product = Product(
        name=data['name'],
        description=data.get('description', ''),
        price=float(data['price']),
        stock=int(data['stock'])
    )
    
    try:
        # Add and commit to database
        db.session.add(new_product)
        db.session.commit()
        
        # Return the created product
        return jsonify(new_product.to_dict()), 201
    except Exception as e:
        # Rollback in case of error
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# Endpoint to get all products
@app.route('/products', methods=['GET'])
def get_products():
    try:
        # Query all products
        products = Product.query.all()
        
        # Convert to list of dictionaries
        products_list = [product.to_dict() for product in products]
        
        return jsonify(products_list), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    

# Endpoint to create a new order
# Example input:

# {
#     "customer_id": 1,
#     "delivery_date": "2024-12-15",
#     "products": [
#         {
#             "product_id": 1,
#             "quantity": 5
#         },
#         {
#             "product_id": 2,
#             "quantity": 8
#         }
#     ]
# }
@app.route('/orders', methods=['POST'])
def create_order():
    # Get data from request
    data = request.get_json()
    
    # Validate input
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    # Check required fields
    if 'customer_id' not in data or 'products' not in data:
        return jsonify({"error": "Customer ID and Products are required"}), 400
    
    try:
        # Find the customer
        customer = Customer.query.get(data['customer_id'])
        if not customer:
            return jsonify({"error": "Customer not found"}), 404
        
        # Create new order
        new_order = Order(
            customer_id=data['customer_id'],
            delivery_date=datetime.fromisoformat(data.get('delivery_date')) if data.get('delivery_date') else None,
            order_total=0.0  # Initialize order total
        )
        
        # First, save the order to get its ID
        db.session.add(new_order)
        db.session.flush()  # This assigns an ID without committing the transaction
        
        # Add products to the order
        for product_data in data['products']:
            # Find the product
            product = Product.query.get(product_data['product_id'])
            if not product:
                db.session.rollback()
                return jsonify({"error": f"Product {product_data['product_id']} not found"}), 404
            
            # Check stock
            quantity = product_data.get('quantity', 1)
            if product.stock < quantity:
                db.session.rollback()
                return jsonify({
                    "error": f"Insufficient stock for product {product.name}. " 
                             f"Requested: {quantity}, Available: {product.stock}"
                }), 400
            
            # Reduce stock
            product.stock -= quantity
            
            # Calculate order total
            new_order.order_total += product.price * quantity
            
            # Insert product to order with quantity using direct SQL
            db.session.execute(
                order_products.insert().values(
                    order_id=new_order.id, 
                    product_id=product.id, 
                    quantity=quantity
                )
            )
        
        # Commit the order, product associations, and stock changes
        db.session.commit()
        
        return jsonify(new_order.to_dict()), 201
    
    except Exception as e:
        # Rollback in case of error
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# Endpoint to get all orders
@app.route('/orders', methods=['GET'])
def get_orders():
    try:
        # Query all orders
        orders = Order.query.all()
        
        # Convert to list of dictionaries
        orders_list = [order.to_dict() for order in orders]
        
        return jsonify(orders_list), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Main entry point
if __name__ == '__main__':
    app.run(debug=True)
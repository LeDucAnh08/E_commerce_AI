// ai-service/graph/seed.cypher
// Chay script nay sau khi co du lieu thuc tu order-service

// 3.5.1 Mo hinh do thi
// Node: User, Product
// Edge: BUY, VIEW, SIMILAR

// 3.5.2 Vi du Cypher
CREATE (u:User {id: 1})
CREATE (p:Product {id: 101})
CREATE (u)-[:BUY]->(p)

// Du lieu mau bo sung
CREATE (u1:User {id: 1, username: 'nguyen_a'})
CREATE (u2:User {id: 2, username: 'tran_b'})

CREATE (p101:Product {id: 101, name: 'Laptop XYZ', category: 'electronics', price: 18500000})
CREATE (p102:Product {id: 102, name: 'Mouse ABC', category: 'electronics', price: 350000})
CREATE (p205:Product {id: 205, name: 'Keyboard K1', category: 'electronics', price: 800000})

CREATE (u1)-[:BUY {timestamp: '2026-04-01'}]->(p101)
CREATE (u1)-[:VIEW {timestamp: '2026-04-02'}]->(p102)
CREATE (u2)-[:BUY {timestamp: '2026-04-03'}]->(p205)

// SIMILAR edges (tinh tu collaborative filtering hoac content similarity)
CREATE (p101)-[:SIMILAR {score: 0.85}]->(p102)
CREATE (p102)-[:SIMILAR {score: 0.72}]->(p205)

// 3.5.3 Truy van goi y
MATCH (u:User {id: 1})-[:BUY]->(p)-[:SIMILAR]->(rec)
RETURN rec

// Truy van goi y Cypher
// Goi y san pham cho User 1:
// Tim cac san pham SIMILAR voi nhung gi User 1 da BUY
MATCH (u:User {id: 1})-[:BUY]->(p)-[:SIMILAR]->(rec:Product)
WHERE NOT (u)-[:BUY]->(rec)
RETURN rec.id, rec.name, rec.price ORDER BY rec.id
LIMIT 5

// Tim users tuong tu (collaborative filtering):
MATCH (u1:User {id: 1})-[:BUY]->(p)<-[:BUY]-(u2:User) WHERE u1 <> u2
MATCH (u2)-[:BUY]->(rec)
WHERE NOT (u1)-[:BUY]->(rec)
RETURN rec.id, count(*) AS freq ORDER BY freq DESC LIMIT 5

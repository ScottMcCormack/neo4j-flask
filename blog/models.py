from py2neo import Graph, Node, Relationship
from py2neo.ext.calendar import GregorianCalendar
from passlib.hash import bcrypt
from datetime import datetime
import uuid


graph = Graph()
calendar = GregorianCalendar(graph)


class User:
    def __init__(self, username):
        self.username = username

    def find(self):
        user = graph.find_one("User", "username", self.username)
        return user

    def register(self, password):
         if not self.find():
            user = Node("User", username=self.username, password=bcrypt.encrypt(password))
            graph.create(user)
            return True

         return False

    def verify_password(self, password):
        user = self.find()

        if not user:
            return False

        return bcrypt.verify(password, user["password"])

    def add_post(self, title, tags, text):
        user = self.find()
        today = datetime.now()

        post = Node(
            "Post",
            id=str(uuid.uuid4()),
            title=title,
            text=text,
            timestamp=int(today.strftime("%s")),
            date=today.strftime("%F")
        )

        rel = Relationship(user, "PUBLISHED", post)
        graph.create(rel)

        today_node = calendar.date(today.year, today.month, today.day).day
        graph.create(Relationship(post, "ON", today_node))

        tags = [x.strip() for x in tags.lower().split(",")]
        tags = set(tags)

        for tag in tags:
            t = Node("Tag", name=tag)
            graph.merge(t)

            rel = Relationship(t, "TAGGED", post)
            graph.create(rel)

    def like_post(self, post_id):
        user = self.find()
        post = graph.find_one("Post", "id", post_id)
        graph.merge(Relationship(user, "LIKES", post))

    def recent_post(self, n):
        query = """
        MATCH (user:User)-[:PUBLISHED]->(post:Post)<-[:TAGGED]-(tag:Tag)
        WHERE user.username = {username}
        RETURN post, COLLECT(tag.name) AS tags
        ORDER BY post.timestamp DESC LIMIT {n}
        """
        return graph.run(query, username=self.username, n=n)

    def similar_users(self, n):
        query = """
        MATCH (user1:User)-[:PUBLISHED]->(:Post)<-[:TAGGED]-(tag:Tag),
              (user2:User)-[:PUBLISHED]->(:Post)<-[:TAGGED]-(tag)
        WHERE user1.username = {username} AND user1 <> user2
        WITH user2, COLLECT(DISTINCT tag.name) AS tags, COUNT(DISTINCT tag.name) AS tag_count
        ORDER BY tag_count DESC LIMIT {n}
        RETURN user2.username AS similar_user, tags
        """
        return graph.run(query, username=self.username, n=n)

    def commonality_of_user(self, user):
        query1 = """
        MATCH (user1:User)-[:PUBLISHED]->(post:Post)<-[:LIKES]-(user2:User)
        WHERE user1.username = {username1} AND user2.username ={username2}
        RETURN COUNT(post) AS likes
        """

        likes = graph.run(query1, username1=self.username, username2=user.username).next()["likes"]

        query2 = """
        MATCH (user1:User)-[:PUBLISHED]->(:Post)<-[:TAGGED]-(tag:Tag),
              (user2:User)-[:PUBLISHED]->(:Post)<-[:TAGGED]-(tag)
        WHERE user1.username = {username1} AND user2.username ={username2}
        RETURN COLLECT(DISTINCT tag.name) AS tags
        """

        tags = graph.run(query2, username1=self.username, username2=user.username).next()["tags"]
        print(tags)

        return {"likes": likes, "tags": tags}


def todays_recent_post(n):
    query = """
        MATCH (user:User)-[:PUBLISHED]->(post:Post)<-[:TAGGED]-(tag:Tag)
        WHERE post.date = {today}
        RETURN user.username AS username, post, COLLECT(tag.name) AS tags
        ORDER BY post.timestamp DESC LIMIT {n}
        """

    today = datetime.now().strftime("%F")
    return graph.run(query, today=today, n=n)
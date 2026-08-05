from app.tools.get_schema import get_schema
from app.tools.execute_query import execute_query
from app.tools.explain_data import explain_data
from app.tools.generate_flowchart import generate_flowchart


class AgentService:

    def get_database_schema(self):
        return get_schema()

    def run_query(self, sql):
        return execute_query(sql)

    def explain(self, question, result):
        return explain_data(question, result)

    def generate_er(self):
        return generate_flowchart()


agent = AgentService()

import openai
from uuid import uuid4

from langchain.prompts import ChatPromptTemplate
from langchain.prompts.chat import SystemMessage, HumanMessagePromptTemplate
import psycopg2
from psycopg2 import sql
import json
from langchain.vectorstores import Chroma
from langchain.document_loaders import JSONLoader
from langchain.document_loaders.csv_loader import CSVLoader

from llm import llm, chat_llm, embeddings
from langchain.memory import ChatMessageHistory
import pandas as pd
from llm import llm, chat_llm
import os



def if_where_in_solution(solution):
    if "where" in solution.lower():
        return True
    else:
        return False


def get_all_the_columns_being_used_in_where_query(solution):
    template = ChatPromptTemplate.from_messages(
            [
                SystemMessage(
                    content=(
                        f"In the below sql query what are different column names being used in where clause?"
                        f"Prepend and append each column name with three backticks '```'"
                    )
                ),
                HumanMessagePromptTemplate.from_template("{sql_query}"),

            ]
        )
    
    answer = chat_llm(template.format_messages(sql_query=solution))
    print(answer.content)
    return answer.content




def gather_all_column_information(query, unique_id, uri_db, relevant_tables_and_columns):
    connection = psycopg2.connect(uri_db)
    cursor = connection.cursor()


    for table_name, column_name, data_type in relevant_tables_and_columns:
        if data_type == 'character varying':
            query = "select distinct " + column_name + " from " + table_name
            print(query)
            cursor.execute(query)
            tables = cursor.fetchall()
            print(tables)

            filename_t = 'csvs/columns_' + unique_id + '___' + table_name + '___' + column_name + '.csv'

            ## Check if csv exists
            if os.path.isfile(filename_t):
                print("File exists")
                continue
            else:
                df = pd.DataFrame(tables, columns=[column_name])
                df.to_csv(filename_t, index=False)
                loader = CSVLoader(file_path=filename_t, encoding="utf8")
                data = loader.load()
                vectordb = Chroma.from_documents(data, embedding=embeddings, persist_directory="./vectors/columns_"+ unique_id + '___' + table_name + '___' + column_name)
                vectordb.persist()
        
    cursor.close()
    connection.close()
    
    ### using query compare against vectors

    all_column_value_info = ''

    for table_name, column_name, data_type in relevant_tables_and_columns:
        if data_type == 'character varying':
            vectordb = Chroma(embedding_function=embeddings, persist_directory="./vectors/columns_"+ unique_id + '___' + table_name + '___' + column_name)
            retriever = vectordb.as_retriever()
            docs = retriever.get_relevant_documents(query)
            print(docs)
            most_relevant_values = []
            for doc in docs:
                most_relevant_values.append(doc.page_content)
            column_value_info = 'Some of the most relevant values in the column ' + column_name + 'of table '+ table_name + ' are: ' + '\n'.join(most_relevant_values) + '\n\n\n'
            all_column_value_info += column_value_info

    return all_column_value_info





def generate_template_for_sql_with_where_clause(query, relevant_tables, table_info, foreign_key_info, additional_table_info, all_column_value_info):
    tables = ",".join(relevant_tables)
    template = ChatPromptTemplate.from_messages(
            [
                SystemMessage(
                    content=(
                        f"You are an assistant that can write SQL Queries."
                        f"Given the text below, write a SQL query that answers the user's question."
                        f"Assume that there is/are SQL table(s) named '{tables}' "
                        f"Here is a more detailed description of the table(s): "
                        f"{table_info}"
                        "Here is some information about some relevant foreign keys:"
                        f"{foreign_key_info}"
                        "Here is some values for some of the relevant columns:"
                        f"{all_column_value_info}"
                        "If in doubt which tables and columns to use, ask the user for more information."
                        "Prepend and append the SQL query with three backticks '```'"
                        
                        
                    )
                ),
                HumanMessagePromptTemplate.from_template("{text}"),

            ]
        )
    
    answer = chat_llm(template.format_messages(text=query))
    print(answer.content)
    return answer.content
    



        
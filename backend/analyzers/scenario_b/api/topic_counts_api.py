# Team: 68 | Name: Yunxiao Gao | Student ID: 1718413
from analytics.topic_counts import get_topic_counts

# RESTful API

def main():

    try:

        result = get_topic_counts()

        return result

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }


# Local Test
if __name__ == "__main__":

    result = main()

    print(result)
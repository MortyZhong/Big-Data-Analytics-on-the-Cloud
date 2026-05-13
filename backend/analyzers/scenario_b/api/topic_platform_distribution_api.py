# Team: 68 | Name: Yunxiao Gao | Student ID: 1718413
from analytics.topic_platform_distribution import (
    get_topic_platform_distribution
)

# =========================
# RESTful API
# =========================

def main():

    try:

        result = get_topic_platform_distribution()

        return result

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }


# =========================
# Local Test
# =========================

if __name__ == "__main__":

    result = main()

    print(result)
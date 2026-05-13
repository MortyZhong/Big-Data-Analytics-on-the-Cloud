from analytics.topic_trends import get_topic_trends

# =========================
# RESTful API
# =========================

def main():

    try:

        result = get_topic_trends()

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
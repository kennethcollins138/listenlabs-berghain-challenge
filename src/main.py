from util import config


def main():
    """
    Goals: 
    1) Fill nightclub with n=1000 people.
    2) need to satisfy constraints such as 
        a) 40% Berlin locals
        b) 80% wearing black
    """
    cfg = config.load_config()
    print(cfg)
     

if __name__ == "__main__":
    main()

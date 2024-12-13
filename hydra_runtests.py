import unittest
import cProfile

if __name__ == '__main__':
    suite = unittest.TestLoader().discover('../test')
    #cProfile.run("unittest.TextTestRunner(verbosity=1).run(suite)", sort='cumtime')
    unittest.TextTestRunner(verbosity=1).run(suite)
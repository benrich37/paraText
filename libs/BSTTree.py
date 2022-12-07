class Node:
    def __init__(self,key,value):
        self.key = key 
        self.value = value
        self.left = None
        self.right = None 

class BST:
    def __init__(self):
        self.root = None
    
    def insertBST(self,root, key,value):
        if root is None:
            root = Node(key,value)
            return root
  
        #Left Subtree 
        elif key < root.key:
            if root.left is None:
                root.left = Node(key,value) 
            else:
                #insertBST(node->left, key)
                self.insertBST(root.left,key,value) 
        #Right Subtree      
        elif key > root.key:
            if root.right is None:
                root.right = Node(key,value) 
            else:
                #insertBST(node->right,key) 
                self.insertBST(root.right,key,value) 
        return root 
    
    def insert(self, key,value):
        self.root = self.insertBST(self.root, key,value)
    
    def inorderBST(self, node):
        if node == None:
            return
        else: 
            self.inorderBST(node.left)
            print(node.key, ':', node.value)
            self.inorderBST(node.right)
            
    def inorder(self):
        self.inorderBST(self.root)

    def searchBST(self, root, key):
        if root is None:
            print(key, "Not found")
            return []
        elif root.key == key:
            return root.value
        elif key > root.key:
            return self.searchBST(root.right, key)
        else:
            return self.searchBST(root.left, key)
        
    def search(self, key):
        return self.searchBST(self.root, key)
    
 
    def deleteAll(self,node):
        if node:
            self.deleteAll(node.left)  
            self.deleteAll(node.right)
            
            node.left = None
            node.right = None
            self.root = None
    
    def deleteAllComplete(self):
        return self.deleteAll(self.root) 
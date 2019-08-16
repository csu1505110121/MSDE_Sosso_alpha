import numpy as np
import pandas as pd
from numpy.linalg import eigvalsh,eigh
from rdkit import Chem
from rdkit.Chem.rdmolops import GetAdjacencyMatrix
from rdkit.Chem.EState import Fingerprinter
from rdkit.Chem import Descriptors
from rdkit.Chem.rdmolops import RDKFingerprint
from rdkit.Chem import AllChem
from rdkit.Chem.Crippen import MolLogP,MolMR
#from sklearn import cross_validation
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel as C
from sklearn.gaussian_process.kernels import Matern, WhiteKernel, ConstantKernel
#from sklearn.model_selection import GridSearchCV
import scipy as sp
from sklearn.base import BaseEstimator
#from sklearn.grid_search import GridSearchCV
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import scale,normalize
from sklearn.model_selection import RepeatedKFold

import networkx as nx
import PYTHON.mol_tree as mt

##############################
## Functions to import data ##
##############################


def MOLfromSMILES(moles):
    def molfromsmiles(mole):
        return Chem.MolFromSmiles(mole)
    vectMFS=np.vectorize(molfromsmiles)
    return vectMFS(moles)


#Extract SMILES and solubility from data in txt file using pandas
def ExtractSMILES(file):
    data=pd.read_table(file,sep=' ',skipfooter=0)
    return data['SMILES'].values


# Convert a single SMILES to RDKIT molecule format
def SMILES2MOL(mole):
    return Chem.MolFromSmiles(mole)


# Convert an array/vector of SMILES data to RDKIT mole format
def SMILES2MOLES(moles):
    vectSMILES2MOL=np.vectorize(SMILES2MOL)
    return vectSMILES2MOL(moles)


# Extract solubility data from txt file using pandas
def ExtractSolub(file):
    data=pd.read_table(file,sep=' ',skipfooter=0)
    return data['Solubility'].values 

def ADDH_MOL(mole):
    return Chem.AddHs(mole)

def ADDH_MOLES(moles):
    vectADDH_MOL=np.vectorize(ADDH_MOL)
    return vectADDH_MOL(moles)

def EMBED_MOL(mole):
    return AllChem.EmbedMolecule(mole)

def EMBED_MOLES(moles):
    vectEMBED_MOL=np.vectorize(EMBED_MOL)
    return vectEMBED_MOL(moles)

#####################################
## Functions to scale/analyze data ##
#####################################

# Returns sum of squared errors for two arrays
def SSE(actual,predict):
    diff=actual-predict
    diff_sq=diff**2
    return np.sum(diff_sq)


def MSE(data1,data2):
    sse=SSE(data1,data2)
    return sse*(1/len(data1))


# Returns the difference in two arrays 
def Diff(actual,predict):
    diff=np.absolute(actual-predict)
    return diff


# normalize a single vector of values to be between [0,1]
def NormalizeVector(data):
    minval=np.min(data)
    maxval=np.max(data)
    spread=maxval-minval
    data_sub_min=data-minval
    return data_sub_min*(1/(spread))


# normalize a each column of values in an np array to be between [0,1]
def NormalizeArray(data): 
    normdata=data.astype(float)
    rows,columns=normdata.shape
    i=0
    while i < columns:
        minval=np.min(data[:,i])
        maxval=np.max(data[:,i])
        spread=float(maxval-minval)
        data_sub_min=data[:,i]-minval
        normal_col=data_sub_min*(1/spread)
        normdata[:,i]=normal_col
        i=i+1
    return normdata


###############################
## Functions for Descriptors ##
###############################


# Function to get adjacency matrix (using RDKIT only to list neighbors)
def AdjMat(mole):
    m=Chem.MolFromSmiles(mole)
    a=m.GetAtoms()
    edges=GetEdges(mole)
    A=np.zeros((len(a),len(a)))
    for edge in edges:
        k,l=edge
        A[k,l]=1
        A[l,k]=1
    return A


# Returns the bond-order matrix for a molecule 
def BondMat(mole):
    edges=GetEdges(mole)
    dim=np.max(edges)+1
    B=np.zeros((dim,dim))
    for edge in edges:
        i,j=edge
        B[i,j]=GetBondType(mole,int(i),int(j))
        B[j,i]=GetBondType(mole,int(i),int(j))
    return B


# Adjacency matrix with user-defined dimension (so that all matrices can have the same dimension)
def GetAdjMat(mole,dim):
    m=Chem.MolFromSmiles(mole)
    edges=GetEdges(mole)
    A=np.zeros((dim,dim))
    for edge in edges:
        k,l=edge
        A[k,l]=1
        A[l,k]=1
    return A


# Bond order matrix with user-defined dimension 
def GetBondMat(mole,dim):
    edges=GetEdges(mole)
    B=np.zeros((dim,dim))
    for edge in edges:
        i,j=edge
        B[i,j]=GetBondType(mole,int(i),int(j))
        B[j,i]=GetBondType(mole,int(i),int(j))
    return B


# Matrix with user-defined dimension, color, weight
def GetColorMat(mole,dim,dikt,color):
    m=Chem.MolFromSmiles(mole)
    atoms=m.GetAtoms()
    edges=GetEdges(mole)
    A=np.zeros((dim,dim))
    for edge in edges:
        k,l=edge
        atomicnumber_k=atoms[int(k)].GetAtomicNum()
        atomicnumber_l=atoms[int(l)].GetAtomicNum()
        polarizability_k=dikt[atomicnumber_k][0]
        polarizability_l=dikt[atomicnumber_l][0]
        if color=='PolarBond': #for polarizability times bond order
            bondorder=GetBondType(mole,int(k),int(l))
            weight=(polarizability_k+polarizability_l)*bondorder
        elif color=='Polar': # for polarizability 
            weight=polarizability_k+polarizability_l
        elif color=='Atomic': # for atomic weight 
            weight=atomicnumber_k+atomicnumber_l
        A[k,l]=weight
        A[l,k]=weight
    return A


# Function to get SPRINT Coordinate for a molecule 
# based on color/matrix, user-defined dimension 
def GetSPRINT(mole,dim,dikt,color):
    m=Chem.MolFromSmiles(mole)
    N=m.GetNumAtoms()
    
    if color=='PolarBond':
        MAT=GetColorMat(mole,dim,dikt,color='PolarBond')
    elif color=='Polar':
        MAT=GetColorMat(mole,dim,dikt,color='Polar')
    elif color=='Atomic':
        MAT=GetColorMat(mole,dim,dikt,color='Atomic')
    elif color=='Bond':
        MAT=GetBondMat(mole,dim)            
    elif color=='Adj':
        MAT=GetAdjMat(mole,dim)
    
    val,vec=eigh(MAT)
    maxval=val[-1]
    maxvec=vec[:,-1]
    SPRINT=np.sort((N**0.5)*maxval*maxvec)
    return SPRINT



###############################
## Functions to get features ##
###############################


# Returns edges/connectivity between atoms of molecule
def GetEdges(mole):
    m=Chem.MolFromSmiles(mole)
    atoms=m.GetAtoms()
    nbrslist=[a.GetNeighbors() for a in atoms]
    edge=[]
    i=0
    for nbrs in nbrslist:
        for n in nbrs:
            edge.append((i,n.GetIdx()))
        i+=1
    G=nx.Graph(list(edge))
    return G.edges()


# Returns the number of atoms for a molecule (in SMILES format)
def NumberOfAtoms(mole):
    m=Chem.MolFromSmiles(mole)
    return m.GetNumAtoms()


# Returns the number of atoms for an array of SMILES data
def GetNumberOfAtoms(moles):
    vectNumberAtoms=np.vectorize(NumberOfAtoms)
    return vectNumberAtoms(moles)


# Returns the principal (largest) eigenvalue of a matrix
def GetPrincipalEigenvalue(matrix):
    from numpy.linalg import eigvalsh
    vals=eigvalsh(matrix)
    return np.max(vals)


# Returns a vector of the eigenvalues of a matrix in descending order
def GetEigenvalues(matrix):
    eigs=eigvalsh(matrix)
    sortedeig=-1*np.sort(-eigs)
    return sortedeig


# Get connectivity from adjacency matrix 
def GetBondOrders(A):                                                
    bonds=[(count_i,count_j) for count_i,i in enumerate(A) for count_j,j in enumerate(i) if count_i < count_j and j == 1]
    return np.array(bonds)


# Returns the bond order between two atoms of a molecule in numerical format
def GetBondType(mole,atom1,atom2):
    bond_dict={Chem.BondType.SINGLE:1.0,Chem.BondType.DOUBLE:2.0,\
               Chem.BondType.TRIPLE:3.0,Chem.BondType.AROMATIC:1.5,\
               Chem.BondType.UNSPECIFIED:0.0}
    m=Chem.MolFromSmiles(mole)
    return bond_dict[m.GetBondBetweenAtoms(atom1,atom2).GetBondType()]


# Gives a list of all bond-orders for a molecule
def GetAllBonds(mole):
    edges=GetEdges(mole)
    return [GetBondType(mole,int(edge[0]),int(edge[1])) for edge in edges]


# Gives a list of the polarizability of all atoms in a molecule
def GetPolarizability(mole,dct):
    m=Chem.MolFromSmiles(mole)
    atoms=m.GetAtoms()
    return [dct[int(a.GetAtomicNum())][0] for a in atoms]


def GetPolarSum(mole,dikt):
    m=Chem.MolFromSmiles(mole)
    atoms=m.GetAtoms()
    edges=GetEdges(mole)
    PBsum=[]
    for edge in edges:
        k,l=edge
        ak=atoms[int(k)].GetAtomicNum()
        al=atoms[int(l)].GetAtomicNum()
        pk=dikt[ak][0]
        pl=dikt[al][0]
        weight=pk+pl
        PBsum.append(weight)
    return PBsum


def GetPolarBondProduct(mole,dikt):
    m=Chem.MolFromSmiles(mole)
    atoms=m.GetAtoms()
    edges=GetEdges(mole)
    PBProduct=[]
    for edge in edges:
        k,l=edge
        ak=atoms[int(k)].GetAtomicNum()
        al=atoms[int(l)].GetAtomicNum()
        pk=dikt[ak][0]
        pl=dikt[al][0]
        bondorder=GetBondType(mole,int(k),int(l))
        weight=(pk+pl)*bondorder
        PBProduct.append(weight)
    return PBProduct


def GetAtomicNumbers(mole):
    m=Chem.MolFromSmiles(mole)
    atoms=m.GetAtoms()
    def Get(x):
        return x.GetAtomicNum()
    GetVector=np.vectorize(Get,otypes=[np.int])
    return GetVector(atoms)




#####################################
## Functions for Clique Vocabulary ##
#####################################


# Obtaining the list of vocabulary for a data set 
def Vocabulary(data):
    cset=set()
    for m in data:
        mol=mt.MolTree(m)
        for c in mol.nodes:
            cset.add(c.smiles)
    return cset


# Creating dictionary for vocab/categorical  
def Vocab2Cat(vocabset):
    vocab=list(vocabset)
    chars=list(np.arange(len(vocabset)))
    MolDict=dict(zip(vocab,chars))
    return MolDict


# Obtaining the clusters for moles in the training set 
def Clusters(data):
    clusters=[]
    for m in data:
        c=[] #using c for clusters
        tree=mt.MolTree(m)
        for node in tree.nodes:
            c.append(node.smiles)
        clusters.append(c)
    return clusters


# Turning each set of clusters for each molecule into categorical labels
def Cluster2Cat(clusters,MolDict):
    cat=[]
    for cluster in clusters:
        l=[]
        for c in cluster:
            l.append(MolDict[c])
        cat.append(l)
    return cat


# Creating vector descriptions from one hot encoded labels of clusters
# size is the number of categorical labels
def Vectorize(catdata,size):
    vectors=[]
    for c in catdata:
        c0=np.array(c).astype(int)
        b=np.zeros((len(c0),size))
        b[np.arange(len(c0)),c0]=1
        b1=b.sum(axis=0)
        vectors.append(b1)
    return vectors


# Want to keep only those moles whose clusters are in 
# the training vocab set
def Discard(testclusters,MolDict):
    testset=[]
    indices=[]
    for i in range(0,len(testclusters)):
        mole=testclusters[i]
        size=len(mole)
        count=0
        for c in mole:
            if c in MolDict:
                count+=1
        if count==size:
            testset.append(mole)
            indices.append(i)
    return testset,indices

def get_kfold_splits(n_splits,descriptors,target,target_column):

    kf = RepeatedKFold(n_splits=n_splits,n_repeats=1, random_state = 10) # set random_state to ensure same split each time

    # Get the train and test splits
    train_test_splits = {'xtrain':[],
                         'xtest':[],
                         'ytrain':[],
                         'ytest':[]}
    for train_index, test_index in kf.split(descriptors, target[target_column]):
        train_test_splits['xtrain'].append(descriptors.loc[train_index,:])
        train_test_splits['xtest'].append(descriptors.loc[test_index,:])
        train_test_splits['ytrain'].append(target[target_column].loc[train_index])
        train_test_splits['ytest'].append(target[target_column].loc[test_index])

    return train_test_splits, train_test_splits, train_test_splits, train_test_splits


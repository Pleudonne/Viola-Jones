import numpy as np

from entrainement_features import *
from retrouver_feature import *
from reconnaitre_visage import *
from creation_features import *


def combinliste(l,k):
    '''l : liste
    k : int
    Renvoie toutes les possibilités de choisir k éléments de l différents
    Par définition, la longueur du résultat est k parmi len(l)'''
    p = []
    i, imax = 0, 2**len(l)-1
    while i<=imax:
        s = []
        j, jmax = 0, len(l)-1
        while j<=jmax:
            if (i>>j)&1==1:
                s.append(l[j])
            j += 1
        if len(s)==k:
            p.append(s)
        i += 1 
    return p


def truncate(n, decimals = 0):
    ''' n : float
    Renvoie la troncature de n avec decimals décimales (par défaut 0)'''
    multiplier = 10 ** decimals 
    return int(n * multiplier) / multiplier


def ensemble_possibilites_somme (l) :
    '''l : liste
    Renvoie tous les résultats possibles de somme des éléments de la liste (éléments, somme de deux éléments, de trois éléments,...)
    triés par ordre décroissant, avec une précision de 1 sur les flottants'''
    n = len(l)
    res = []
    for i in range(1,n+1) :
        possibilites = combinliste(l,i)
        for possibilite in possibilites :
            s = sum(possibilite)
            if s > 0.1 :
                res.append(truncate(s,1))
    return np.flipud(np.unique(res))



def construction_cascade(f,d,F_target,P,N,test_visage,test_non_visage) :
    ''' f : float -> le taux de faux positifs maximal par couche de la cascade
    d : float -> le taux de détection minimal par couche de la cascade
    F_target : float -> le taux de faux positifs maximal pour la cascade en entier
    N : ndarray(3) -> la base de données d'entraînement de non-visages
    P :  ndarray(3) -> la base de données d'entraînement de non-visages
    test_visage : ndarray(3) -> la base de données de test de visages
    test_non_visage : ndarray(3) -> la base de données de test de non-visages'''

    longueur_test_visage = len(test_visage)
    longueur_test_non_visage = len(test_non_visage)

    features_positifs = eval_feature(P) # la valeur de toutes les features possibles sur la base de données d'entraînement de visages
    nombre_images_visages = len (P)

    F = [1.] # le taux de faux positifs des classifieurs forts de la cascade, initialisé à 1
    D = [1.] # le taux de détection des classifieurs fort de la cascades, initialisé à 1

    i = 0 # le numéro du classifieur fort de la cascade

    fonction_cascade = []

    while F[i] > F_target :
        n = 0
        i += 1
        F.append(F[-1])
        D.append(0.)

        # comme la base de données d'entraînement de non-visages change à chaque nouveau classifieur fort, on doit la réévaluer à chaque fois
        features_negatifs = eval_feature(N)

        indice_tri_positifs,indice_tri_negatifs,valeurs_feature_positifs,valeurs_feature_negatifs,intervalle,i_plus,i_moins = \
            preliminaire_entrainement_classifieurs_faibles (P,N,features_positifs,features_negatifs,linspace=False)

        nombre_images_non_visages = len (N)

        # pour l'heure, aucune image n'a de raison d'avoir plus de poids que les autres
        poids_visages = (1/(nombre_images_visages+nombre_images_non_visages)) * np.ones (nombre_images_visages)
        poids_non_visages = (1/(nombre_images_visages+nombre_images_non_visages)) * np.ones (nombre_images_non_visages)

        classifieur_fort = []


        while F[i] > f*F[i-1] :
            n += 1
            fonction_cascade.append(0)
            # dans la suite du code, on applique l'algorithme d'Adaboost (on est obligé de le réécrire car on ne sait pas à l'avance le nombre
            # de classifieurs faibles dans le classifieur fort de la cascade)

            t1 = time()

            somme = np.sum(poids_visages)+np.sum(poids_non_visages)
            poids_visages /= somme
            poids_non_visages /= somme

            # on entraîne itérativement les classifieurs faibles avec les poids des images qui évoluent
            classifieurs = entrainement_classifieurs_faibles (P,N,poids_visages,poids_non_visages,features_positifs,features_negatifs, \
                                            indice_tri_positifs,indice_tri_negatifs,valeurs_feature_positifs,valeurs_feature_negatifs,intervalle,i_plus,i_moins)

            # le tableau des erreurs de chaque classifieur
            erreurs = np.array([e[3] for e in classifieurs])

            indice_erreur_min = int(np.argmin(erreurs))
        
            # on rajoute 10^-300 à l'erreur minimale car une erreur nulle pose des problèmes de définition de fonctions
            erreur_min = max(erreurs[indice_erreur_min],0) + 1E-300
            meilleur_classifieur = classifieurs[indice_erreur_min]

            beta = erreur_min / (1. - erreur_min)
            alpha = np.log(1. / beta)

            # on parcourt les images pour mettre à jour leur poids
            # si la classification est correcte, le poids est multiplié par beta < 1, sinon il est inchangé
            # on rappelle que meilleur_classifieur contient comme premier élément la valeur de la ième feature
            # pour toute la base de données de visage (indice 0 à nombre_images_visages - 1) et de la base de
            # données de non-visages (des indices nombre_images_visages à nombre_images_visages + nombre_images_non_visages)
        
            for l in range(nombre_images_visages) :
                if visage_classifieur(meilleur_classifieur,l) :  # classification correcte
                    poids_visages[l] *= beta

            for l in range(nombre_images_non_visages) :
                if not visage_classifieur(meilleur_classifieur,l+nombre_images_visages) :  # classification correcte
                    poids_non_visages[l] *= beta

            # on n'oublie pas de considérer l'erreur à laquelle on a rajouté 10^-300
            feature, polarite, seuil,_ = meilleur_classifieur
            classifieur_fort.append([indice_erreur_min, polarite, seuil, erreur_min, alpha])

            print ("Le classifieur faible défini par :\n      numéro de feature : ",indice_erreur_min,"\n", \
                "     polarité : ",polarite,"\n","     seuil : ",seuil,"\n","     erreur : ",erreur_min,"\n", "     alpha : ",alpha,"\n", \
                "a été déterminé en ",int((time()-t1)*100)/100," secondes","\n\n")


            # maintenant qu'on a rajouté un classifieur faible, on recalcule la condition minimale permettant d'atteindre un taux de détection
            # au moins supérieur à d*D[i-1]

            # les poids des classifieurs faibles
            alphas = [classifieur_fort[i][4] for i in range(len(classifieur_fort))]

            # toutes les valeurs de conditions possibles :
            # si le nombre de classifieurs faibles dans le classifieurs forts de la cascade est trop élevée, considérer
            # l'ensemble des sommes possibles est beaucoup trop coûteux (taille de liste de l'ordre de 2**n : somme des k parmi n)
            # on fera alors une discrétisation à pas constant de 0.1 avec la valeur maximale de condtion comme étant sum(alphas)
            # selon cette dernière méthode, la taille de la liste est 10*sum(alphas)
            s = truncate(sum(alphas),1)

            if 2**n < 10*s :
                conditions = ensemble_possibilites_somme(alphas)
            else :
                conditions = np.arange(s,0,-0.1)

            # on rajoute -1 pour s'assurer que la prochaine boucle s'arrête (voir plus loin)
            conditions = np.concatenate((conditions,np.array([-1.])))

            visages_corrects = 0
            # on crée un tableau différent pour le calcul du taux de détection car on va le modifier pour gagner du temps d'exécution
            verification_visage = np.array(test_visage)

            # on remet à zéro le taux de détection pour le recalculer ensuite
            D[i] = 0.

            j = 0

            # tant que le taux de détection n'est pas convenable (il le sera forcément à une certaine condition, comme conditions contient -1)
            while D[i] < d*D[i-1] :

                condition = conditions[j]

                # en diminuant la condition, les visages déjà reconnus le seront toujours, on peut donc gagner du temps d'exécution en ne
                # les testant pas pour le calcul de D à la prochaine boucle
                a_conserver = np.ones(len(verification_visage),dtype=bool)

                for k,visage in enumerate(verification_visage) :
                    if monolithique (visage,classifieur_fort,features,condition) :  # classification correcte
                        visages_corrects += 1
                        a_conserver[k] = False # on ne testera plus cette image à la prochaine boucle

                # on notera par la suite que visages_corrects n'est pas réincrémentée à 0 car les images déjà reconnues comme visage
                # le seront toujours en diminuant le seuil
                D[i] = visages_corrects / longueur_test_visage

                verification_visage = verification_visage[a_conserver] # on enlève les images déjà bien reconnues

                j += 1
            
            # une fois que le taux de détection est valide, on peut déterminer le taux de faux positifs

            fonction_cascade[-1] = ([classifieur_fort,condition])
            n = len(fonction_cascade)
            fonction = [fonction_cascade[i][0] for i in range(n)] # la fonction de détection
            conditions = [fonction_cascade[i][1] for i in range(n)] # les conditions pour chaque classifieur fort
            non_visages_incorrects = 0

            for non_visage in test_non_visage :
                if cascade (non_visage,fonction,features,conditions) :  # classification incorrecte
                    non_visages_incorrects += 1

            F[i] = non_visages_incorrects / longueur_test_non_visage


        if F[i] > F_target :
            a_conserver = np.zeros(len(N),dtype=bool)

            for k,non_visage in enumerate(N) :
                a_conserver[k] = cascade (non_visage,fonction,features,conditions) # classification incorrecte

            N = N[a_conserver]

    return fonction_cascade


def seuil_monolithique (test_visage,f,taux_detection,features,precision_condition=0.1) :
    '''Entrée : test_visage : numpy array (3) -> la base de données test d'images de visages : une dimension 
                    pour le nombre d'images et les deux autres pour les dimensions de chacune des images
                f : numpy array (2) -> le classifieur fort total (trié par ordre décroissant des poids)
                taux_detection : float -> le taux de détection visé
                features : list -> liste des coordonnées des points à soustraire avec les largeurs que l'on associe à un numéro de feature
                precision_condition : float -> le pas pour la recherche du seuil optimal


    Sortie : seuil : float -> le seuil de détection pour savoir si ce groupement de classifieurs faibles considère
                         une image comme un visage (si supérieur au seuil) ou non

    Pour la recherche du seuil, on a décidé dans cette fonction de ne prendre en considération que le taux de détection souhaité
    '''

    nombre_images_visages = len (test_visage)

    condition = -precision_condition # un seuil trop faible pour l'heure

    # on crée un tableau contenant la valeur du détecteur pour toutes les images de la base de données
    detecteur_bdd = np.zeros(nombre_images_visages)

    for i,visage in enumerate(test_visage) :

        poids = 0
        for numero,polarite,seuil,_,alpha in f :
            numero = int (numero)
            if polarite == 1 :
                if valeur_feature (features[numero],visage) < seuil :
                    poids += alpha
            else :
                if valeur_feature (features[numero],visage) > seuil :
                    poids += alpha

        detecteur_bdd[i] = poids

    D = 1. # le taux de détection (comme le seuil est négatif initialement, D vaut 1)
    incorrects = 0 # le nombre de visages mal classifiés, initialement aucun

    # on augmente le seuil pour que le taux de détection du classifieur fort soit supérieur
    # à taux_detection et que le seuil soit le plus faible possible
    # tant que D est convenable, on le recalcule avec le nouveau seuil
    while D > taux_detection :
        
        condition += precision_condition
        print(detecteur_bdd,D,condition)
        n1 = len(detecteur_bdd)
        detecteur_bdd = detecteur_bdd[detecteur_bdd > condition] # on ne conserve que les images bien classifiées
        n2 = len(detecteur_bdd)

        incorrects += n1 - n2 # les nouvelles images mal classifiées

        D = 1 - (incorrects / nombre_images_visages) # le taux de détection avec la condition de la boucle

    return (condition-precision_condition) # de sorte à ce que le taux de détection soit bien convenable




if __name__ == "__main__" :
    
    taille = 24 # taille minimale des carrés balayés (24 x 24 pour la méthode de Viola-Jones)
    pas = 2 # pas entre chaque sous-rectangles dans les carrés balayés
    increment = 1.2 # ce par quoi on multiplie itérativement la taille des sous-rectangles
    features = retrouver_features(taille,pas,increment) # toutes les features avec ces paramètres
    
    # Tests des fonctions combinliste, ensemble_possibilites_somme et truncate
    # Pour l'implémentation de combinliste, nous nous sommes basés sur la fonction implémentée à cette adresse :
    # https://python.jpvweb.com/python/mesrecettespython/doku.php?id=combinaisons
    l = list(range(1,43,6))
    print (combinliste(l,3))
    print (ensemble_possibilites_somme(l))

    print(truncate(42.123,1))

    # Construction de la cascade
    f = # le taux de faux positifs maximal par couche de la cascade, à compléter
    d = # le taux de détection minimal par couche de la cascade, à compléter
    F_target = # le taux de faux positifs maximal pour la cascade en entier, à compléter

    P = np.load("chemin") # la base de données d'entraînement de non-visages, chemin à compléter
    N = np.load("chemin") # la base de données d'entraînement de non-visages, chemin à compléter

    test_visage = np.load("chemin") # la base de données de test de visages, chemin à compléter
    test_non_visage = np.load("chemin") # la base de données de test de non-visages, chemin à compléter

    fonction_cascade = construction_cascade(f,d,F_target,P,N,test_visage,test_non_visage)
    print(fonction_cascade)
    np.save("cascade.npy",fonction_cascade)
    
    # le seuil trouvé pour la fonction de détection monolithique
    f = np.load("fonction_detection.npy")
    print (seuil_monolithique (test_visage,f,d,features))
